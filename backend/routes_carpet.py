import secrets
from datetime import date, timedelta
from typing import Dict, List

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from comms import add_event, log_comm, upsert_lead
from core import audit, company_name, current_actor, current_company, get_settings, now, now_iso, oid, out, outs, require_owner, tdb
from pricing import fmt_date
from routes_public import EMAIL_RE, PhotoRef, notify_owner, tenant_from_slug
from storage import attach_photos

public = APIRouter(prefix="/api/public/{slug}/carpet-quotes", dependencies=[Depends(tenant_from_slug)])
admin = APIRouter(prefix="/api/admin/carpet-quotes", dependencies=[Depends(require_owner)])
AREAS = {"living_room": "Living room carpets", "bedroom": "Bedroom carpets", "hallway": "Hallway carpets", "stairs": "Carpeted stairs",
         "landing": "Carpeted landings", "office": "Office carpets", "commercial": "Commercial carpets", "other": "Other carpeted areas"}
ANSWERS = {"visible_stains": "Visible stains", "heavily_soiled": "Heavily soiled", "concerns": "Marks or areas of concern", "pets": "Pets in the property",
           "pet_hair": "Pet hair on the carpets", "pet_urine": "Pet urine stains", "pet_odour": "Pet-related odours",
           "stain_treatment": "Stain treatment requested", "odour_treatment": "Pet odour treatment requested"}
ACK = ("Thank you for your carpet cleaning enquiry. Your request has been received and is awaiting review. We will assess your requirements and contact you "
       "with a quote. Your booking is not confirmed until we approve the appointment and confirm the details with you.")


class Contact(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=6, max_length=30)
    email: str = Field(pattern=EMAIL_RE)


class CarpetIn(BaseModel):
    areas: Dict[str, int] = Field(min_length=1, max_length=8)
    other_areas: str = Field("", max_length=500)
    stairs_steps: int = Field(0, ge=0, le=200)
    stairs_landing: str = Field("", max_length=20)
    answers: Dict[str, str] = Field({}, max_length=12)
    notes: str = Field("", max_length=2000)
    photos: List[PhotoRef] = Field([], max_length=10)
    preferred_date: str
    preferred_time: str = Field(min_length=1, max_length=20)
    contact: Contact
    postcode: str = Field(min_length=2, max_length=10)
    address: str = Field(min_length=5, max_length=250)
    marketing_consent: bool = False


def summary(q: dict) -> str:
    areas = ", ".join(f"{AREAS[k]} x{v}" for k, v in q["areas"].items())
    stairs = f" Stairs: {q['stairs_steps']} steps, landing: {q.get('stairs_landing') or '-'}." if "stairs" in q["areas"] else ""
    ans = " ".join(f"{ANSWERS[k]}: {v}." for k, v in q.get("answers", {}).items() if v)
    return f"Areas: {areas}.{stairs} {ans} {q.get('other_areas') or ''} {q.get('notes') or ''}".strip()


@public.post("")
async def request_quote(body: CarpetIn):
    if any(k not in AREAS or not 1 <= v <= 50 for k, v in body.areas.items()):
        raise HTTPException(422, "Please choose the areas that need cleaning.")
    if "stairs" in body.areas and body.stairs_steps < 1:
        raise HTTPException(422, "Please tell us how many carpeted steps need cleaning.")
    if any(k not in ANSWERS or len(v) > 500 for k, v in body.answers.items()):
        raise HTTPException(422, "One of the answers is not valid.")
    try:
        if date.fromisoformat(body.preferred_date) <= now().date():
            raise HTTPException(422, "Please choose a preferred date in the future.")
    except ValueError:
        raise HTTPException(422, "Please choose a valid preferred date.")
    if await tdb.carpet_quotes.count_documents({"contact.email": body.contact.email, "created_at": {"$gte": (now() - timedelta(hours=24)).isoformat()}}) >= 3:
        raise HTTPException(429, "We've already received your requests today - our team will be in touch. You can also call us.")
    s = await get_settings()
    lead_id = await upsert_lead({**body.contact.model_dump(), "postcode": body.postcode}, "website", "Carpet cleaning quote requested",
                                {"marketing_consent": body.marketing_consent})
    doc = {**body.model_dump(exclude={"photos"}), "postcode": body.postcode.upper(), "status": "awaiting_review", "lead_id": lead_id,
           "history": [{"at": now_iso(), "text": "Request received"}], "created_at": now_iso()}
    qid = str((await tdb.carpet_quotes.insert_one(doc)).inserted_id)
    n = await attach_photos(body.photos, carpet_quote_id=qid, lead_id=lead_id)
    when = f"{fmt_date(body.preferred_date)} {body.preferred_time}"
    await notify_owner(s, f"Carpet cleaning quote request - {body.contact.name}",
                       f"{body.contact.name} ({body.contact.phone}, {body.contact.email}) at {body.address}, {body.postcode.upper()}. Preferred: {when} (request only). "
                       f"{summary(doc)} Photos: {n}. Review it and send a quote in the dashboard under Carpet quotes.", lead_id)
    await log_comm(body.contact.email, "email", "carpet_quote_ack", "We've received your carpet cleaning enquiry",
                   f"Hi {body.contact.name},\n\n{ACK}\n\nYour preferred time ({when}) is a request, not a confirmed appointment.", lead_id=lead_id)
    return {"ok": True, "id": qid, "message": ACK}


def _check(q):
    if not q:
        raise HTTPException(404, "Request not found")


def _check_token(q, t: str):
    if not q or not q.get("token") or not secrets.compare_digest(q["token"], t) or q["status"] not in ("quoted", "accepted", "confirmed"):
        raise HTTPException(404, "This quote link is not valid")


@public.get("/{qid}")
async def view_quote(qid: str, t: str):
    q = await tdb.carpet_quotes.find_one({"_id": oid(qid)})
    _check_token(q, t)
    return {"status": q["status"], "price": q["quote"]["price"], "date": q["quote"]["date"], "time": q["quote"]["time"], "message": q["quote"].get("message", ""),
            "first_name": q["contact"]["name"].split()[0], "areas": [f"{AREAS[k]} x{v}" for k, v in q["areas"].items()],
            "stairs_steps": q.get("stairs_steps") if "stairs" in q["areas"] else None, "address": f"{q['address']}, {q['postcode']}"}


class AcceptIn(BaseModel):
    t: str
    pay_terms_accepted: bool = False
    origin_url: str


@public.post("/{qid}/accept")
async def accept_quote(qid: str, body: AcceptIn):
    q = await tdb.carpet_quotes.find_one({"_id": oid(qid)})
    _check_token(q, body.t)
    if q["status"] != "quoted":
        raise HTTPException(409, "This quote has already been accepted.")
    if not body.pay_terms_accepted:
        raise HTTPException(409, "Please confirm you accept the Terms and Conditions before paying.")
    terms = {p["key"]: p["published_version"] async for p in tdb.policies.find({"require_acceptance": True, "published_version": {"$gt": 0}, "unpublished": {"$ne": True}})}
    qt, c = q["quote"], q["contact"]
    await tdb.bookings.update_many({"carpet_quote_id": qid, "status": "pending_payment"}, {"$set": {"status": "abandoned"}})
    lead = await tdb.leads.find_one({"_id": oid(q["lead_id"])})
    booking = {"lead_id": q["lead_id"], "quote_id": None, "carpet_quote_id": qid, "customer": c, "postcode": q["postcode"], "address": q["address"],
               "service": "carpet", "service_name": "Carpet Cleaning", "input": {"address": q["address"], "postcode": q["postcode"], "property_notes": summary(q)},
               "lines": [{"label": "Carpet cleaning (as quoted)", "amount": qt["price"]}], "total": qt["price"], "deposit_amount": qt["price"], "balance_due": 0,
               "payment_mode": "full_upfront", "date": qt["date"], "slot": qt["time"], "access": {}, "access_notes": "", "tip": 0,
               "status": "pending_payment", "payment_status": "pending", "source": (lead or {}).get("source", "website"), "accepted_policies": terms,
               "pay_terms_confirmed_at": now_iso(), "reference": f"{current_company.get()['slug'][:2].upper()}-{now().strftime('%y%m')}-{secrets.token_hex(3).upper()}",
               "hold_expires_at": (now() + timedelta(minutes=30)).isoformat(), "created_at": now_iso()}
    bid = str((await tdb.bookings.insert_one(booking)).inserted_id)
    origin = body.origin_url.rstrip("/")
    session = stripe.checkout.Session.create(
        mode="payment", customer_email=c["email"], metadata={"booking_id": bid, "kind": "carpet"},
        line_items=[{"quantity": 1, "price_data": {"currency": "gbp", "unit_amount": int(round(qt["price"] * 100)),
                     "product_data": {"name": f"Carpet Cleaning - {fmt_date(qt['date'])} {qt['time']}"}}}],
        success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}", cancel_url=f"{origin}/payment/cancel?booking_id={bid}")
    await tdb.payment_transactions.insert_one({"session_id": session.id, "booking_id": bid, "amount": float(qt["price"]), "kind": "carpet", "currency": "gbp",
                                              "status": "initiated", "payment_status": "pending", "created_at": now_iso(), "updated_at": now_iso()})
    await tdb.bookings.update_one({"_id": oid(bid)}, {"$set": {"session_id": session.id}})
    return {"checkout_url": session.url}


async def settle_carpet(tx: dict):
    res = await tdb.bookings.update_one({"_id": oid(tx["booking_id"]), "status": {"$in": ["pending_payment", "abandoned"]}},
                                       {"$set": {"status": "awaiting_approval", "payment_status": "paid", "paid_at": now_iso()}})
    if not res.modified_count:
        return
    b = await tdb.bookings.find_one({"_id": oid(tx["booking_id"])})
    when = f"{fmt_date(b['date'])} {b['slot']}"
    await tdb.carpet_quotes.update_one({"_id": oid(b["carpet_quote_id"])}, {"$set": {"status": "accepted", "booking_id": str(b["_id"])},
                                                                         "$push": {"history": {"at": now_iso(), "text": f"Quote accepted and £{b['total']:.2f} paid - awaiting your approval"}}})
    await add_event(b["lead_id"], "payment", f"Carpet quote accepted and paid (£{b['total']:.2f}) - awaiting approval")
    await log_comm(b["customer"]["email"], "email", "carpet_payment_received", "Payment received - awaiting approval",
                   f"Hi {b['customer']['name']}, thank you - we've received your payment of £{b['total']:.2f} for carpet cleaning on {when} (ref {b['reference']}). "
                   "Your booking is not confirmed until we approve the appointment. We'll be in touch shortly to confirm.", lead_id=b["lead_id"])
    await notify_owner(await get_settings(), f"Carpet quote accepted & paid - {b['customer']['name']}",
                       f"{b['customer']['name']} accepted and paid £{b['total']:.2f} for {when}. Approve the appointment in the dashboard under Carpet quotes.", b["lead_id"])


@admin.get("")
async def list_quotes():
    return outs(await tdb.carpet_quotes.find({}, {"token": 0}).sort("created_at", -1).to_list(300))


@admin.get("/{qid}")
async def get_quote(qid: str):
    q = await tdb.carpet_quotes.find_one({"_id": oid(qid)})
    _check(q)
    q.pop("token", None)
    photos = await tdb.photos.find({"carpet_quote_id": qid, "status": "attached", "is_deleted": False}, {"token": 0, "path": 0}).to_list(20)
    return {"quote": out(q), "photos": outs(photos)}


class QuoteOut(BaseModel):
    price: float = Field(ge=1, le=20000)
    date: str
    time: str = Field(min_length=1, max_length=20)
    message: str = Field("", max_length=2000)


@admin.post("/{qid}/quote")
async def send_quote(qid: str, body: QuoteOut, request: Request):
    q = await tdb.carpet_quotes.find_one({"_id": oid(qid)})
    _check(q)
    if q["status"] not in ("awaiting_review", "quoted"):
        raise HTTPException(400, f"This request is already {q['status'].replace('_', ' ')}")
    try:
        if date.fromisoformat(body.date) <= now().date():
            raise HTTPException(422, "Choose an appointment date in the future")
    except ValueError:
        raise HTTPException(422, "Choose a valid appointment date")
    token = q.get("token") or secrets.token_urlsafe(16)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    url = f"https://{host}/carpet-cleaning/quote/{qid}?t={token}"
    c = q["contact"]
    status = await log_comm(c["email"], "email", "carpet_quote_sent", f"Your carpet cleaning quote - £{body.price:.2f}",
                            f"Hi {c['name']},\n\nThank you for your carpet cleaning enquiry. Having reviewed your details and photos, our price is £{body.price:.2f} "
                            f"for an appointment on {fmt_date(body.date)} at {body.time}. {body.message}\n\nPlease use the secure link below to review and accept your quote "
                            "and pay. Your booking is not confirmed until we approve the appointment.\n\nKind regards,\n" + company_name(),
                            lead_id=q["lead_id"], link=("Review & accept your quote", url))
    await tdb.carpet_quotes.update_one({"_id": q["_id"]}, {"$set": {"status": "quoted", "token": token, "quote": {**body.model_dump(), "sent_at": now_iso(), "by": current_actor.get()}},
                                                           "$push": {"history": {"at": now_iso(), "text": f"Quote sent: £{body.price:.2f} for {fmt_date(body.date)} {body.time}"}}})
    await add_event(q["lead_id"], "quote", f"Carpet cleaning quote sent: £{body.price:.2f}")
    await audit("carpet.quote", f"{c['name']} £{body.price:.2f}")
    return {"url": url, "email_status": status}


@admin.post("/{qid}/approve")
async def approve(qid: str):
    q = await tdb.carpet_quotes.find_one({"_id": oid(qid)})
    _check(q)
    b = await tdb.bookings.find_one({"_id": oid(q.get("booking_id")), "status": "awaiting_approval"}) if q.get("booking_id") else None
    if q["status"] != "accepted" or not b:
        raise HTTPException(400, "Only accepted and paid quotes can be approved")
    await tdb.bookings.update_one({"_id": b["_id"]}, {"$set": {"status": "confirmed", "approved_at": now_iso()}})
    await tdb.carpet_quotes.update_one({"_id": q["_id"]}, {"$set": {"status": "confirmed"}, "$push": {"history": {"at": now_iso(), "text": "Appointment approved - booking confirmed"}}})
    await tdb.leads.update_one({"_id": oid(b["lead_id"])}, {"$set": {"status": "booked"}})
    c, when = b["customer"], f"{fmt_date(b['date'])} at {b['slot']} (ref {b['reference']})"
    await add_event(b["lead_id"], "booking", f"Carpet cleaning booking confirmed: {when}")
    await log_comm(c["email"], "email", "booking_confirmation", f"Booking confirmed - {when}",
                   f"Hi {c['name']}, your carpet cleaning is now confirmed for {when} at {b['address']} {b['postcode']}. Payment of £{b['total']:.2f} received. "
                   "Our Terms and Conditions apply to this booking.", lead_id=b["lead_id"])
    remind_at = (date.fromisoformat(b["date"]) - timedelta(days=1)).isoformat() + "T17:00:00+00:00"
    await log_comm(c["email"], "email", "appointment_reminder", f"Reminder: your carpet cleaning is tomorrow - {when}",
                   f"Hi {c['name']}, a quick reminder that your carpet cleaning with {company_name()} is booked for {when}. Please make sure we can access the property.",
                   lead_id=b["lead_id"], scheduled_for=remind_at)
    await audit("carpet.approve", b["reference"])
    return {"ok": True}


class DeclineIn(BaseModel):
    message: str = Field("", max_length=2000)


@admin.post("/{qid}/decline")
async def decline(qid: str, body: DeclineIn):
    q = await tdb.carpet_quotes.find_one({"_id": oid(qid)})
    _check(q)
    if q["status"] in ("confirmed", "declined"):
        raise HTTPException(400, f"This request is already {q['status']}")
    paid = await tdb.bookings.find_one({"_id": oid(q["booking_id"]), "status": "awaiting_approval"}) if q.get("booking_id") else None
    note = "Request declined"
    if paid:
        refund = {"amount": paid["total"], "rule_percent": 100, "suggested": paid["total"], "notice_hours": None, "note": "Declined before approval",
                  "status": "to_issue_in_stripe", "recorded_at": now_iso(), "recorded_by": current_actor.get()}
        await tdb.bookings.update_one({"_id": paid["_id"]}, {"$set": {"status": "cancelled", "payment_status": "refund_due", "refund": refund}})
        note += f" - full refund of £{paid['total']:.2f} recorded (issue it in Stripe)"
    await tdb.carpet_quotes.update_one({"_id": q["_id"]}, {"$set": {"status": "declined"}, "$push": {"history": {"at": now_iso(), "text": note}}})
    refund_text = f" A full refund of £{paid['total']:.2f} will be made to your original payment method." if paid else ""
    await log_comm(q["contact"]["email"], "email", "carpet_quote_declined", "Your carpet cleaning enquiry",
                   f"Hi {q['contact']['name']},\n\nThank you for your carpet cleaning enquiry. Unfortunately we are unable to go ahead with this request. {body.message}{refund_text}"
                   f"\n\nKind regards,\n{company_name()}", lead_id=q["lead_id"])
    await add_event(q["lead_id"], "quote", note)
    return {"ok": True}
