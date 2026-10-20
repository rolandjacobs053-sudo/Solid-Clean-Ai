import json
import logging
import secrets
import os
from datetime import timedelta, date
from typing import Dict, List, Literal, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from comms import add_event, booking_link, log_comm, quote_email, upsert_lead
from core import access_state, company_name, current_company, db, get_settings, now, now_iso, oid, out, plan_features, set_tenant, tdb
from pricing import compute_quote, fmt_date, slots_for
from storage import attach_photos


async def tenant_from_slug(slug: str):
    company = await db.companies.find_one({"slug": slug})
    if not company:
        raise HTTPException(404, "Company not found")
    if not access_state(company)["ok"]:
        raise HTTPException(402, "This company's online booking is temporarily unavailable.")
    set_tenant(company)
    return company


router = APIRouter(prefix="/api")
public = APIRouter(prefix="/api/public/{slug}", dependencies=[Depends(tenant_from_slug)])
logger = logging.getLogger(__name__)
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
SOURCES = {"website", "seo", "google_ads", "ai_chat", "phone", "cold_email", "referral", "whatsapp", "other"}
EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class QuoteIn(BaseModel):
    service: str
    property_type: str = "flat"
    bedrooms: int = Field(1, ge=0, le=12)
    bathrooms: int = Field(1, ge=0, le=10)
    living_rooms: int = Field(1, ge=0, le=6)
    condition: str = "good"
    extras: List[str] = []
    extra_qty: Dict[str, int] = Field({}, max_length=40)
    postcode: str = ""
    date: str = ""
    promo_code: str = ""
    address: str = Field("", max_length=200)
    furnished: str = Field("", max_length=30)
    pets: str = Field("", max_length=30)
    pet_hair_odour: bool = False
    additional_areas: List[str] = Field([], max_length=10)
    flooring: str = Field("", max_length=30)
    property_notes: str = Field("", max_length=1000)


class PhotoRef(BaseModel):
    id: str
    token: str


class AccessIn(BaseModel):
    method: Literal["customer_present", "authorised_person", "estate_agency", "other"] = "customer_present"
    person_name: str = Field("", max_length=120)
    person_phone: str = Field("", max_length=30)
    agency_name: str = Field("", max_length=120)
    agency_address: str = Field("", max_length=250)
    agency_instructions: str = Field("", max_length=1000)
    notes: str = Field("", max_length=1000)


ACCESS_LABELS = {"customer_present": "Customer will be present", "authorised_person": "Authorised person will give access",
                 "estate_agency": "Keys collected from estate agency", "other": "Other arrangement"}


class Contact(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(pattern=EMAIL_RE)
    phone: str = Field(min_length=6, max_length=30)
    marketing_consent: bool = False


class QuoteSave(BaseModel):
    quote: QuoteIn
    contact: Contact
    source: str = "website"
    photos: List[PhotoRef] = Field([], max_length=10)


class BookingIn(QuoteSave):
    date: str
    slot: str
    access_notes: str = ""
    access: AccessIn = AccessIn()
    accepted_policies: dict = {}
    pay_terms_accepted: bool = False
    tip: float = Field(0, ge=0, le=500)
    quote_id: Optional[str] = None
    origin_url: str


class OptOut(BaseModel):
    email: str = Field(pattern=EMAIL_RE)


class TipIn(BaseModel):
    t: str
    amount: float = Field(ge=1, le=500)
    origin_url: str


def _source(s: str) -> str:
    return s if s in SOURCES else "website"


async def store_quote(q: dict, result: dict, lead_id, source: str, conversation_id=None, status=None) -> str:
    doc = {"input": q, "result": result, "total": result.get("total"), "service_name": result.get("service_name"),
           "status": status or ("sent" if result["status"] == "ok" else "needs_review"), "lead_id": lead_id, "source": source,
           "conversation_id": conversation_id, "follow_ups_sent": 0, "created_at": now_iso()}
    return str((await tdb.quotes.insert_one(doc)).inserted_id)


async def notify_owner(settings: dict, subject: str, body: str, lead_id=None):
    await log_comm(settings["business"]["owner_notify_email"], "email", "owner_notification", subject, body, lead_id=lead_id)


def deposit_for(settings: dict, total: float) -> float:
    return round(total * 0.5, 2) if settings["business"].get("payment_mode") == "deposit_50" else total


def access_text(a: dict) -> str:
    parts = [ACCESS_LABELS.get(a.get("method"), "-")]
    if a.get("method") == "authorised_person":
        parts.append(f"{a.get('person_name')} {a.get('person_phone')}")
    if a.get("method") == "estate_agency":
        parts.append(f"{a.get('agency_name')}, {a.get('agency_address')}. {a.get('agency_instructions') or ''}")
    if a.get("notes"):
        parts.append(a["notes"])
    return " - ".join(p.strip() for p in parts if p.strip())


@router.get("/")
async def root():
    return {"service": "Solid Clean OS", "ok": True}


@public.get("/config")
async def public_config(slug: str):
    s = await get_settings()
    company = await db.companies.find_one({"slug": slug})
    feats = await plan_features(company)
    return {"pricing": s["pricing"], "availability": s["availability"], "knowledge_base": s["knowledge_base"],
            "ai_receptionist": company.get("comped") or "ai_receptionist" in feats,
            "policies": [{k: p.get(k) for k in ("key", "title", "published_version", "published_content", "effective_date", "require_acceptance")}
                         async for p in tdb.policies.find({"audience": "public", "published_version": {"$gt": 0}, "unpublished": {"$ne": True}}).sort("order", 1)],
            "business": {k: s["business"].get(k) for k in ("name", "website", "online_payments", "phone", "logo_url", "brand_primary", "brand_accent", "about_text", "contact_email", "service_areas_text", "business_hours", "payment_mode")}}


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(pattern=EMAIL_RE)
    phone: str = Field("", max_length=30)
    message: str = Field(min_length=2, max_length=3000)
    marketing_consent: bool = False


@public.post("/contact")
async def contact(body: ContactIn):
    s = await get_settings()
    lead_id = await upsert_lead(body.model_dump(), "website", f"Contact form: {body.message[:300]}", {"marketing_consent": body.marketing_consent})
    await notify_owner(s, "New website contact message", f"{body.name} {body.phone} {body.email}: {body.message}", lead_id)
    return {"ok": True}


@public.get("/reviews")
async def public_reviews():
    rows = await tdb.reviews.find({"demo": {"$ne": True}}).sort("review_date", -1).to_list(100)
    return [{"author": r["author"], "rating": r["rating"], "text": r.get("text", ""), "review_date": r["review_date"], "platform": r.get("platform"),
             "response": r.get("response") if r.get("status") == "approved" else ""} for r in rows]


@public.post("/quote/preview")
async def quote_preview(q: QuoteIn):
    s = await get_settings()
    result = compute_quote(s["pricing"], q.model_dump())
    if result.get("total") is not None:
        result["deposit"] = deposit_for(s, result["total"])
    return result


@public.get("/availability")
async def availability(date: str):
    return {"date": date, "slots": await slots_for((await get_settings())["availability"], date)}


@public.post("/quotes")
async def save_quote(body: QuoteSave, request: Request):
    s = await get_settings()
    q = body.quote.model_dump()
    result = compute_quote(s["pricing"], q)
    if result["status"] == "invalid":
        raise HTTPException(400, "Unknown service")
    src = _source(body.source)
    lead_id = await upsert_lead({**body.contact.model_dump(), "postcode": q["postcode"]}, src,
                                f"Quote requested: {result['service_name']}" + (f" £{result['total']:.2f}" if result.get("total") else ""),
                                {"marketing_consent": body.contact.marketing_consent})
    await tdb.leads.update_one({"_id": oid(lead_id), "status": "new"}, {"$set": {"status": "quoted"}})
    quote_id = await store_quote(q, result, lead_id, src)
    await attach_photos(body.photos, lead_id=lead_id, quote_id=quote_id)
    if result["status"] == "ok":
        await log_comm(body.contact.email, "email", "quote_sent", f"Your {company_name()} quote - £{result['total']:.2f}",
                       quote_email(body.contact.name, result), lead_id=lead_id, link=booking_link(request, current_company.get()["slug"], quote_id))
    else:
        await log_comm(body.contact.email, "email", "enquiry_ack", "We've received your enquiry",
                       f"Hi {body.contact.name}, thanks for your enquiry. A member of our team will review the details and contact you shortly.", lead_id=lead_id)
        await notify_owner(s, "Enquiry needs manual quote", f"{body.contact.name} ({body.contact.phone}): {'; '.join(result['reasons'])}", lead_id)
    return {"quote_id": quote_id, "result": result}


@public.get("/quotes/{quote_id}")
async def get_quote(quote_id: str):
    q = await tdb.quotes.find_one({"_id": oid(quote_id)})
    if not q:
        raise HTTPException(404, "Quote not found")
    inp = {k: v for k, v in q["input"].items() if k != "address"}
    return {"id": quote_id, "input": inp, "result": q["result"]}


@public.post("/bookings")
async def create_booking(body: BookingIn):
    s = await get_settings()
    q = {**body.quote.model_dump(), "date": body.date}
    result = compute_quote(s["pricing"], q)
    required = {p["key"]: p["published_version"] async for p in tdb.policies.find({"require_acceptance": True, "published_version": {"$gt": 0}, "unpublished": {"$ne": True}})}
    if any(body.accepted_policies.get(k) != v for k, v in required.items()):
        raise HTTPException(409, "Please review and accept the current booking terms and policies.")
    if not body.pay_terms_accepted:
        raise HTTPException(409, "Please confirm you accept the Terms and Conditions before paying.")
    if q["service"] == "carpet":
        raise HTTPException(422, "Carpet cleaning is quoted after we review your request. Please use the carpet cleaning quote form.")
    if result["status"] != "ok":
        raise HTTPException(422, "This booking needs a quick review by our team: " + " ".join(result["reasons"]))
    if len(q["address"].strip()) < 5:
        raise HTTPException(422, "Please enter the property address.")
    a = body.access
    if a.method == "estate_agency" and not (a.agency_name.strip() and a.agency_address.strip()):
        raise HTTPException(422, "Please add the estate agency name and address for key collection.")
    if a.method == "authorised_person" and not (a.person_name.strip() and a.person_phone.strip()):
        raise HTTPException(422, "Please add the name and phone number of the person giving access.")
    if body.slot not in [x["slot"] for x in await slots_for(s["availability"], body.date)]:
        raise HTTPException(409, "Sorry, that slot is no longer available. Please choose another time.")
    contact = body.contact.model_dump()
    lead_id = await upsert_lead({**contact, "postcode": q["postcode"]}, _source(body.source),
                                f"Booking started: {result['service_name']} on {fmt_date(body.date)} {body.slot}",
                                {"marketing_consent": body.contact.marketing_consent})
    lead = await tdb.leads.find_one({"_id": oid(lead_id)})
    quote_id = body.quote_id if body.quote_id and await tdb.quotes.find_one({"_id": oid(body.quote_id)}) else None
    if quote_id:
        await tdb.quotes.update_one({"_id": oid(quote_id)}, {"$set": {"lead_id": lead_id, "input": q, "result": result, "total": result["total"]}})
    else:
        quote_id = await store_quote(q, result, lead_id, lead["source"], status="booking_started")
    charge, tip = deposit_for(s, result["total"]), round(body.tip, 2)
    booking = {"tip": tip, "pay_terms_confirmed_at": now_iso(), "lead_id": lead_id, "quote_id": quote_id, "customer": {k: contact[k] for k in ("name", "email", "phone")},
               "postcode": q["postcode"].upper(), "address": q["address"].strip(), "service": q["service"], "service_name": result["service_name"], "input": q,
               "lines": result["lines"], "total": result["total"], "deposit_amount": charge, "balance_due": round(result["total"] - charge, 2),
               "payment_mode": s["business"].get("payment_mode", "full_upfront"), "date": body.date, "slot": body.slot,
               "access": a.model_dump(), "access_notes": body.access_notes or access_text(a.model_dump()),
               "status": "pending_payment", "payment_status": "pending", "source": lead["source"], "accepted_policies": required,
               "reference": f"{current_company.get()['slug'][:2].upper()}-{now().strftime('%y%m')}-{secrets.token_hex(3).upper()}", "promo_code": result.get("promo_applied"),
               "hold_expires_at": (now() + timedelta(minutes=30)).isoformat(), "created_at": now_iso()}
    booking_id = str((await tdb.bookings.insert_one(booking)).inserted_id)
    await attach_photos(body.photos, booking_id=booking_id, lead_id=lead_id, quote_id=quote_id)
    if not s["business"].get("online_payments", True):
        await finalize_booking(booking_id, paid=False)
        return {"confirmed": True, "booking_id": booking_id, "payment_instructions": s["business"].get("payment_instructions", "")}
    origin = body.origin_url.rstrip("/")
    kwargs = dict(
        mode="payment", customer_email=body.contact.email, metadata={"booking_id": booking_id},
        line_items=[{"quantity": 1, "price_data": {"currency": "gbp", "unit_amount": int(round(charge * 100)), "tax_behavior": "inclusive",
                     "product_data": {"name": ("50% deposit - " if charge < result["total"] else "") + f"{result['service_name']} - {fmt_date(body.date)} {body.slot}"}}}]
        + ([{"quantity": 1, "price_data": {"currency": "gbp", "unit_amount": int(round(tip * 100)), "tax_behavior": "inclusive",
                                           "product_data": {"name": "Tip for your cleaning team"}}}] if tip > 0 else []),
        success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin}/payment/cancel?booking_id={booking_id}")
    try:
        session = stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True}, billing_address_collection="required")
    except stripe.error.StripeError:
        session = stripe.checkout.Session.create(**kwargs)
    await tdb.payment_transactions.insert_one({"session_id": session.id, "booking_id": booking_id, "amount": float(round(charge + tip, 2)), "tip": tip, "kind": "deposit" if charge < result["total"] else "booking",
                                              "currency": "gbp", "status": "initiated", "payment_status": "pending",
                                              "created_at": now_iso(), "updated_at": now_iso()})
    await tdb.bookings.update_one({"_id": oid(booking_id)}, {"$set": {"session_id": session.id}})
    return {"checkout_url": session.url, "booking_id": booking_id}


@public.post("/bookings/{booking_id}/release")
async def release_booking(booking_id: str):
    await tdb.bookings.update_one({"_id": oid(booking_id), "status": "pending_payment"}, {"$set": {"status": "abandoned"}})
    return {"ok": True}


async def finalize_booking(booking_id: str, paid: bool = True):
    pending = await tdb.bookings.find_one({"_id": oid(booking_id)}, {"balance_due": 1})
    deposit = paid and (pending or {}).get("balance_due", 0) > 0
    res = await tdb.bookings.update_one({"_id": oid(booking_id), "status": "pending_payment"},
                                       {"$set": {"status": "confirmed", "payment_status": ("deposit_paid" if deposit else "paid") if paid else "due", "paid_at": now_iso() if paid else None}})
    if not res.modified_count:
        return
    b = await tdb.bookings.find_one({"_id": oid(booking_id)})
    s = await get_settings()
    when = f"{fmt_date(b['date'])} at {b['slot']} (ref {b.get('reference', '-')})"
    c = b["customer"]
    if b.get("promo_code"):
        await tdb.settings.update_one({"pricing.promo_codes.code": b["promo_code"]}, {"$inc": {"pricing.promo_codes.$.uses": 1}})
    pay_text = (f"Deposit of £{b['deposit_amount']:.2f} received. The remaining balance of £{b['balance_due']:.2f} is due immediately after the clean." if deposit
                else f"Payment of £{b['total'] + (b.get('tip') or 0):.2f} received" + (f" (including a £{b['tip']:.2f} tip - thank you!)." if b.get("tip") else ".") if paid else f"Amount due: £{b['total']:.2f}. {s['business'].get('payment_instructions', '')}")
    await tdb.leads.update_one({"_id": oid(b["lead_id"])}, {"$set": {"status": "booked"}})
    await tdb.quotes.update_one({"_id": oid(b["quote_id"])}, {"$set": {"status": "accepted"}})
    await add_event(b["lead_id"], "booking", f"Booking confirmed ({'deposit paid' if deposit else 'paid'}): {b['service_name']} {when} (£{b['total']:.2f})")
    await log_comm(c["email"], "email", "booking_confirmation", f"Booking confirmed - {when}",
                   f"Hi {c['name']}, your {b['service_name']} is confirmed for {when} at {b.get('address') or ''} {b['postcode']}. {pay_text} "
                   "To reschedule, please give us at least 48 hours' notice. Our company policy applies to this booking.", lead_id=b["lead_id"])
    await log_comm(c["phone"], "sms", "booking_confirmation", "Booking confirmed",
                   f"{company_name()}: your clean is confirmed for {when}. Reply or call us to make changes.", lead_id=b["lead_id"])
    await notify_owner(s, f"New booking - {when}", f"{c['name']} {c['phone']} - {b['service_name']} at {b.get('address') or ''} {b['postcode']}, total £{b['total']:.2f}. {pay_text} Access: {b.get('access_notes') or '-'}", b["lead_id"])
    remind_at = (date.fromisoformat(b["date"]) - timedelta(days=1)).isoformat() + "T17:00:00+00:00"
    await log_comm(c["phone"], "sms", "appointment_reminder", "Reminder",
                   f"Reminder: {company_name()} is booked for {when}. Please ensure access as discussed.", lead_id=b["lead_id"], scheduled_for=remind_at)
    await log_comm(c["email"], "email", "appointment_reminder", f"Reminder: your clean is tomorrow - {when}",
                   f"Hi {c['name']}, a quick reminder that your {b['service_name']} with {company_name()} is booked for {when} at {b['postcode']}. "
                   "Please make sure we can access the property as discussed. To make changes, reply to this email or call us.",
                   lead_id=b["lead_id"], scheduled_for=remind_at)


async def settle_balance(tx: dict):
    res = await tdb.bookings.update_one({"_id": oid(tx["booking_id"]), "payment_status": "deposit_paid"},
                                       {"$set": {"payment_status": "paid", "balance_due": 0, "balance_paid_at": now_iso()}})
    if res.modified_count:
        b = await tdb.bookings.find_one({"_id": oid(tx["booking_id"])})
        await add_event(b["lead_id"], "payment", f"Balance of £{tx['amount']:.2f} paid for booking {b.get('reference')}")


async def settle_tip(tx: dict):
    res = await tdb.payment_transactions.update_one({"session_id": tx["session_id"], "settled": {"$ne": True}}, {"$set": {"settled": True}})
    if res.modified_count:
        await tdb.bookings.update_one({"_id": oid(tx["booking_id"])}, {"$inc": {"after_tip": tx["amount"]}, "$set": {"after_tip_paid_at": now_iso()}})
        b = await tdb.bookings.find_one({"_id": oid(tx["booking_id"])})
        await add_event(b["lead_id"], "payment", f"Tip of £{tx['amount']:.2f} received for booking {b.get('reference')}")
        await notify_owner(await get_settings(), f"Tip received - £{tx['amount']:.2f}",
                           f"{b['customer']['name']} left a £{tx['amount']:.2f} tip for the {b['service_name']} on {fmt_date(b['date'])} (ref {b.get('reference')}, cleaner: {b.get('assigned_name') or 'unassigned'}).", b["lead_id"])


async def settle_tx(tx: dict, booking_id: str):
    kind = tx.get("kind")
    if kind == "carpet":
        from routes_carpet import settle_carpet
        return await settle_carpet(tx)
    await (settle_balance(tx) if kind == "balance" else settle_tip(tx) if kind == "tip" else finalize_booking(booking_id))


async def _tip_booking(booking_id: str, t: str) -> dict:
    b = await tdb.bookings.find_one({"_id": oid(booking_id)})
    if not b or b.get("status") != "completed" or not b.get("tip_token") or not secrets.compare_digest(b["tip_token"], t):
        raise HTTPException(404, "This tip link is not valid")
    return b


@public.get("/tips/{booking_id}")
async def tip_info(booking_id: str, t: str):
    b = await _tip_booking(booking_id, t)
    return {"service_name": b["service_name"], "date": b["date"], "first_name": b["customer"]["name"].split()[0],
            "cleaner": (b.get("assigned_name") or "").split(" ")[0], "tips_received": b.get("after_tip") or 0}


@public.post("/tips/{booking_id}")
async def tip_checkout(booking_id: str, body: TipIn):
    b = await _tip_booking(booking_id, body.t)
    amount, origin = round(body.amount, 2), body.origin_url.rstrip("/")
    session = stripe.checkout.Session.create(
        mode="payment", customer_email=b["customer"]["email"], metadata={"booking_id": booking_id, "kind": "tip"},
        line_items=[{"quantity": 1, "price_data": {"currency": "gbp", "unit_amount": int(round(amount * 100)),
                     "product_data": {"name": f"Tip for your cleaning team - {b['service_name']} {fmt_date(b['date'])}"}}}],
        success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}", cancel_url=f"{origin}/tip/{booking_id}?t={body.t}")
    await tdb.payment_transactions.insert_one({"session_id": session.id, "booking_id": booking_id, "amount": float(amount), "kind": "tip",
                                              "currency": "gbp", "status": "initiated", "payment_status": "pending", "created_at": now_iso(), "updated_at": now_iso()})
    return {"checkout_url": session.url}


@router.get("/payments/status/{session_id}")
async def payment_status(session_id: str):
    tx = await db.payment_transactions.find_one({"session_id": session_id, "kind": {"$ne": "subscription"}})
    if not tx:
        raise HTTPException(404, "Transaction not found")
    set_tenant(await db.companies.find_one({"_id": oid(tx["company_id"])}))
    if tx["payment_status"] != "paid":
        try:
            sess = stripe.checkout.Session.retrieve(session_id)
            if sess.payment_status == "paid":
                await tdb.payment_transactions.update_one({"session_id": session_id, "payment_status": {"$ne": "paid"}},
                                                         {"$set": {"status": "completed", "payment_status": "paid", "updated_at": now_iso()}})
                tx = await tdb.payment_transactions.find_one({"session_id": session_id})
        except stripe.error.StripeError:
            pass
    if tx["payment_status"] == "paid":
        await settle_tx(tx, tx["booking_id"])
    b = await tdb.bookings.find_one({"_id": oid(tx["booking_id"])})
    return {"session_id": session_id, "status": tx["status"], "payment_status": tx["payment_status"], "kind": tx.get("kind", "booking"), "amount": tx["amount"],
            "booking": {"service_name": b["service_name"], "date": b["date"], "slot": b["slot"], "total": b["total"], "reference": b.get("reference")}}


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    try:
        event = stripe.Webhook.construct_event(await request.body(), request.headers.get("stripe-signature", ""), WEBHOOK_SECRET)
    except (stripe.error.SignatureVerificationError, ValueError):
        raise HTTPException(400, "Invalid signature")
    obj, kind = json.loads(str(event["data"]["object"])), event["type"]
    from routes_saas import handle_billing_event
    if await handle_billing_event(kind, obj):
        return {"status": "ok"}
    tx = await db.payment_transactions.find_one({"session_id": obj.get("id")})
    if not tx or tx.get("kind") == "subscription":
        return {"status": "ignored"}
    set_tenant(await db.companies.find_one({"_id": oid(tx["company_id"])}))
    if kind == "checkout.session.completed" and obj.get("payment_status") == "paid":
        await tdb.payment_transactions.update_one({"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
                                                 {"$set": {"status": "completed", "payment_status": "paid", "updated_at": now_iso()}})
        tx = await tdb.payment_transactions.find_one({"session_id": obj["id"]})
        await settle_tx(tx, obj["metadata"]["booking_id"])
    elif kind == "checkout.session.expired":
        await tdb.payment_transactions.update_one({"session_id": obj["id"]}, {"$set": {"status": "expired", "payment_status": "expired"}})
        await tdb.bookings.update_one({"session_id": obj["id"], "status": "pending_payment"}, {"$set": {"status": "abandoned"}})
    return {"status": "ok"}


@public.post("/optout")
async def opt_out(body: OptOut):
    email = body.email.lower().strip()
    await tdb.suppressions.update_one({"email": email}, {"$setOnInsert": {"reason": "unsubscribe_link", "created_at": now_iso()}}, upsert=True)
    await tdb.prospects.update_many({"email": email}, {"$set": {"status": "opted_out"}})
    await tdb.leads.update_many({"email": email}, {"$set": {"marketing_consent": False}})
    return {"ok": True}
