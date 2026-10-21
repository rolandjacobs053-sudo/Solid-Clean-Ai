import re
import secrets
from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from comms import add_event, log_comm
from core import audit, current_company, db, get_settings, now, now_iso, oid, out, outs, require_admin, tdb
from pricing import fmt_date

router = APIRouter(prefix="/api/admin/customers", dependencies=[Depends(require_admin)])
TIME_RE = r"^([01]\d|2[0-3]):[0-5]\d$"
ACTIVE = ("confirmed", "awaiting_approval", "pending_payment")
CONTACT = ("phone", "email", "whatsapp", "walk_in", "referral", "website", "other")


class CustomerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(default="", max_length=30)
    email: str = Field(default="", max_length=160)
    address: str = Field(default="", max_length=300)
    postcode: str = Field(default="", max_length=10)
    service_interest: str = Field(default="", max_length=60)
    property_details: str = Field(default="", max_length=1500)
    requirements: str = Field(default="", max_length=1500)
    notes: str = Field(default="", max_length=3000)
    contact_method: str = "phone"
    type: Literal["residential", "commercial"] = "residential"
    marketing_consent: bool = False


class BookingIn(BaseModel):
    service: str
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    slot: str = Field(pattern=TIME_RE)
    duration_hours: float = Field(default=3, gt=0, le=14)
    price: float = Field(ge=0, le=100000)
    payment_status: Literal["paid", "due", "deposit_paid"] = "due"
    amount_paid: float = Field(default=0, ge=0)
    payment_method: str = Field(default="", max_length=60)
    address: str = Field(default="", max_length=300)
    postcode: str = Field(default="", max_length=10)
    requirements: str = Field(default="", max_length=2000)
    special_instructions: str = Field(default="", max_length=2000)
    assigned_to: Optional[str] = None
    send_confirmation: bool = False
    allow_conflict: bool = False


class BookingEdit(BaseModel):
    date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    slot: Optional[str] = Field(default=None, pattern=TIME_RE)
    duration_hours: Optional[float] = Field(default=None, gt=0, le=14)
    price: Optional[float] = Field(default=None, ge=0, le=100000)
    payment_status: Optional[Literal["paid", "due", "deposit_paid"]] = None
    amount_paid: Optional[float] = Field(default=None, ge=0)
    requirements: Optional[str] = Field(default=None, max_length=2000)
    special_instructions: Optional[str] = Field(default=None, max_length=2000)
    notify_customer: bool = False
    allow_conflict: bool = False


def _clean(body: CustomerIn) -> dict:
    d = body.model_dump()
    d["email"] = d["email"].lower().strip() or None
    d["phone"] = d["phone"].replace(" ", "") or None
    d["postcode"] = d["postcode"].upper().strip()
    if d["contact_method"] not in CONTACT:
        d["contact_method"] = "other"
    if d["email"] and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", d["email"]):
        raise HTTPException(422, "Please enter a valid email address")
    if not (d["email"] or d["phone"]):
        raise HTTPException(422, "Add at least a phone number or an email address")
    return d


def _mins(t: str) -> int:
    h, m = (t or "08:00")[:5].split(":")
    return int(h) * 60 + int(m)


async def conflicts(day: str, slot: str, hours: float, assigned_to, lead_id: str, exclude=None):
    s = await get_settings()
    start, end = _mins(slot), _mins(slot) + int(hours * 60)
    q = {"date": day, "status": {"$in": list(ACTIVE)}}
    if exclude:
        q["_id"] = {"$ne": exclude}
    hits = []
    for b in await tdb.bookings.find(q, {"timeline": 0, "input": 0, "lines": 0}).to_list(200):
        bs = _mins(b.get("slot"))
        if bs < end and start < bs + int((b.get("duration_hours") or 3) * 60):
            hits.append(b)
    hard = [b for b in hits if b.get("lead_id") == lead_id or (assigned_to and b.get("assigned_to") == assigned_to)]
    summary = [{"id": str(b["_id"]), "reference": b.get("reference"), "slot": b.get("slot"), "customer": (b.get("customer") or {}).get("name"),
                "service": b.get("service_name"), "assigned_name": b.get("assigned_name"), "double_booking": b in hard} for b in hits]
    over_capacity = len(hits) >= s["availability"]["capacity_per_slot"]
    return summary, bool(hard), over_capacity


def _check(summary, hard, over, allow):
    if hard:
        raise HTTPException(409, {"message": "Double booking: this customer or the assigned cleaner already has a job at that time.", "conflicts": summary})
    if over and not allow:
        raise HTTPException(409, {"message": "Scheduling conflict: that time is already at full team capacity. Confirm to book anyway.", "conflicts": summary, "can_override": True})


async def _customer(cid: str) -> dict:
    c = out(await tdb.leads.find_one({"_id": oid(cid)}, {"timeline": 0}))
    if not c or c.get("erased"):
        raise HTTPException(404, "Customer not found")
    return c


@router.get("")
async def list_customers(q: str = ""):
    query = {"erased": {"$ne": True}}
    if q.strip():
        rx = {"$regex": re.escape(q.strip().replace(" ", "") if q.strip().replace(" ", "").isdigit() else q.strip()), "$options": "i"}
        query["$or"] = [{f: rx} for f in ("name", "email", "phone", "postcode", "address")]
    leads = outs(await tdb.leads.find(query, {"timeline": 0}).sort("updated_at", -1).to_list(500))
    stats = {}
    async for b in tdb.bookings.find({"lead_id": {"$in": [lead["id"] for lead in leads]}, "status": {"$ne": "abandoned"}}, {"lead_id": 1, "status": 1, "date": 1, "total": 1, "payment_status": 1, "balance_due": 1}):
        st = stats.setdefault(b["lead_id"], {"bookings": 0, "upcoming": 0, "completed": 0, "spend": 0.0, "last_date": None})
        st["bookings"] += 1
        st["upcoming"] += b["status"] == "confirmed" and b["date"] >= now().date().isoformat()
        st["completed"] += b["status"] == "completed"
        st["spend"] += float(b.get("total") or 0) - float(b.get("balance_due") or 0) if b.get("payment_status") in ("paid", "deposit_paid") else 0
        st["last_date"] = max(st["last_date"] or "", b["date"])
    return [{**lead, "stats": stats.get(lead["id"], {"bookings": 0, "upcoming": 0, "completed": 0, "spend": 0, "last_date": None})} for lead in leads]


@router.post("")
async def create_customer(body: CustomerIn):
    d = _clean(body)
    dup = await tdb.leads.find_one({"erased": {"$ne": True}, "$or": [x for x in ({"email": d["email"]} if d["email"] else None, {"phone": d["phone"]} if d["phone"] else None) if x]}, {"name": 1})
    if dup:
        raise HTTPException(409, {"message": f"A customer with this email or phone already exists: {dup.get('name')}", "existing_id": str(dup["_id"])})
    doc = {**d, "source": d["contact_method"], "status": "new", "follow_up_date": None, "is_customer": True,
           "timeline": [{"at": now_iso(), "type": d["contact_method"], "text": f"Customer profile created manually (contacted by {d['contact_method']})"}],
           "consent_recorded_at": now_iso() if d["marketing_consent"] else None, "created_at": now_iso(), "updated_at": now_iso()}
    cid = str((await tdb.leads.insert_one(doc)).inserted_id)
    await audit("customer.create", f"{cid} {d['name']}")
    return {"id": cid}


@router.get("/{cid}")
async def get_customer(cid: str):
    c = await _customer(cid)
    lead = await tdb.leads.find_one({"_id": oid(cid)}, {"timeline": 1})
    return {"customer": c, "timeline": (lead.get("timeline") or [])[-50:][::-1],
            "bookings": outs(await tdb.bookings.find({"lead_id": cid, "status": {"$ne": "abandoned"}}, {"input": 0, "lines": 0}).sort([("date", -1), ("slot", -1)]).to_list(200)),
            "quotes": outs(await tdb.quotes.find({"lead_id": cid}, {"input": 0, "result": 0}).sort("created_at", -1).to_list(50)),
            "communications": outs(await tdb.communications.find({"lead_id": cid}).sort("created_at", -1).to_list(100)),
            "plans": outs(await tdb.recurring_plans.find({"lead_id": cid}).to_list(20))}


@router.put("/{cid}")
async def update_customer(cid: str, body: CustomerIn):
    await _customer(cid)
    d = _clean(body)
    await tdb.leads.update_one({"_id": oid(cid)}, {"$set": {**d, "updated_at": now_iso()}})
    await add_event(cid, "profile", "Customer details updated")
    await audit("customer.update", cid)
    return {"ok": True}


@router.delete("/{cid}")
async def erase_customer(cid: str, ctx=Depends(require_admin)):
    if ctx["user"]["role"] != "owner":
        raise HTTPException(403, "Only the account owner can erase customer data")
    await _customer(cid)
    if await tdb.bookings.count_documents({"lead_id": cid, "status": "confirmed", "date": {"$gte": now().date().isoformat()}}):
        raise HTTPException(409, "This customer has upcoming bookings. Cancel them before erasing their data.")
    anon = {"name": "Erased customer", "email": None, "phone": None, "address": "", "property_details": "", "requirements": "", "notes": "", "erased": True,
            "erased_at": now_iso(), "timeline": [], "marketing_consent": False}
    await tdb.leads.update_one({"_id": oid(cid)}, {"$set": anon})
    await tdb.bookings.update_many({"lead_id": cid}, {"$set": {"customer": {"name": "Erased customer", "email": "", "phone": ""}, "address": "", "access_notes": "", "special_instructions": ""}})
    await tdb.communications.delete_many({"lead_id": cid})
    await audit("customer.erase", f"{cid} personal data erased (UK GDPR request); financial booking records kept anonymised")
    return {"ok": True}


@router.post("/{cid}/conflicts")
async def check_conflicts(cid: str, body: BookingIn):
    summary, hard, over = await conflicts(body.date, body.slot, body.duration_hours, body.assigned_to, cid)
    return {"conflicts": summary, "double_booking": hard, "over_capacity": over}


@router.post("/{cid}/bookings")
async def create_booking(cid: str, body: BookingIn):
    c = await _customer(cid)
    s = await get_settings()
    svc = next((x for x in s["pricing"]["services"] if x["key"] == body.service), None)
    if not svc:
        raise HTTPException(400, "Unknown service")
    if body.date < (now().date() - timedelta(days=60)).isoformat():
        raise HTTPException(422, "That date is too far in the past")
    _check(*await conflicts(body.date, body.slot, body.duration_hours, body.assigned_to, cid), body.allow_conflict)
    staff = await db.users.find_one({"_id": oid(body.assigned_to), "company_id": current_company.get()["id"]}) if body.assigned_to else None
    paid = body.price if body.payment_status == "paid" else min(body.amount_paid, body.price) if body.payment_status == "deposit_paid" else 0
    doc = {"lead_id": cid, "customer": {"name": c["name"], "email": c.get("email") or "", "phone": c.get("phone") or ""},
           "address": body.address or c.get("address", ""), "postcode": (body.postcode or c.get("postcode") or "").upper(),
           "service": svc["key"], "service_name": svc["name"], "date": body.date, "slot": body.slot, "duration_hours": body.duration_hours,
           "total": round(body.price, 2), "deposit_amount": round(paid, 2), "balance_due": round(body.price - paid, 2),
           "payment_status": body.payment_status, "payment_method": body.payment_method, "paid_at": now_iso() if paid else None,
           "requirements": body.requirements, "special_instructions": body.special_instructions, "access_notes": body.special_instructions,
           "assigned_to": body.assigned_to or None, "assigned_name": staff["name"] if staff else None,
           "status": "confirmed", "manual": True, "source": c.get("contact_method") or c.get("source") or "manual",
           "reference": f"{current_company.get()['slug'][:2].upper()}-{now().strftime('%y%m')}-{secrets.token_hex(3).upper()}",
           "created_at": now_iso(), "updated_at": now_iso()}
    bid = str((await tdb.bookings.insert_one(doc)).inserted_id)
    await tdb.leads.update_one({"_id": oid(cid)}, {"$set": {"status": "booked", "is_customer": True, "updated_at": now_iso()}})
    await add_event(cid, "booking", f"Manual booking created: {svc['name']} {fmt_date(body.date)} {body.slot} (£{body.price:.2f}, {body.payment_status})")
    await audit("booking.manual_create", f"{doc['reference']} {c['name']}")
    if body.send_confirmation:
        await _notify(doc, "confirmed")
    return {"id": bid, "reference": doc["reference"]}


async def _notify(b: dict, kind: str):
    c, when = b["customer"], f"{fmt_date(b['date'])} at {b['slot']} (ref {b.get('reference', '-')})"
    if not c.get("email"):
        return
    pay = "Paid in full - thank you." if b["payment_status"] == "paid" else f"Amount due: £{b['balance_due']:.2f}."
    subject = f"Booking {'confirmed' if kind == 'confirmed' else 'updated'} - {when}"
    await log_comm(c["email"], "email", "booking_confirmation" if kind == "confirmed" else "booking_rescheduled", subject,
                   f"Hi {c['name']}, your {b['service_name']} is {'confirmed' if kind == 'confirmed' else 'now booked'} for {when} at {b.get('address') or ''} {b['postcode']}. {pay} "
                   "To make changes, please reply to this email or call us with at least 48 hours' notice.", lead_id=b["lead_id"])
    await tdb.communications.update_many({"lead_id": b["lead_id"], "status": "scheduled", "template": "appointment_reminder"}, {"$set": {"status": "cancelled"}})
    remind_at = (date.fromisoformat(b["date"]) - timedelta(days=1)).isoformat() + "T17:00:00+00:00"
    if remind_at > now_iso():
        await log_comm(c["email"], "email", "appointment_reminder", f"Reminder: your clean is tomorrow - {when}",
                       f"Hi {c['name']}, a quick reminder that your {b['service_name']} is booked for {when}. Please make sure we can access the property as discussed.",
                       lead_id=b["lead_id"], scheduled_for=remind_at)


@router.patch("/bookings/{bid}")
async def edit_booking(bid: str, body: BookingEdit):
    b = await tdb.bookings.find_one({"_id": oid(bid)}, {"timeline": 0})
    if not b:
        raise HTTPException(404, "Booking not found")
    if b["status"] in ("cancelled", "completed"):
        raise HTTPException(409, f"This booking is {b['status']} and can't be changed")
    upd = {k: v for k, v in body.model_dump(exclude={"notify_customer", "allow_conflict"}).items() if v is not None}
    if not b.get("manual") and ({"price", "payment_status", "amount_paid"} & upd.keys()):
        raise HTTPException(409, "Price and payment for online card bookings are managed by Stripe - use refunds or balance links instead.")
    moved = any(k in upd and upd[k] != b.get(k) for k in ("date", "slot", "duration_hours"))
    if moved:
        _check(*await conflicts(upd.get("date", b["date"]), upd.get("slot", b["slot"]), upd.get("duration_hours", b.get("duration_hours") or 3), b.get("assigned_to"), b["lead_id"], b["_id"]), body.allow_conflict)
    if "price" in upd or "payment_status" in upd or "amount_paid" in upd:
        price = upd.pop("price", b["total"])
        ps = upd.get("payment_status", b["payment_status"])
        paid = price if ps == "paid" else min(upd.pop("amount_paid", b.get("deposit_amount") or 0), price) if ps == "deposit_paid" else 0
        upd.update({"total": round(price, 2), "deposit_amount": round(paid, 2), "balance_due": round(price - paid, 2), "payment_status": ps})
        upd.pop("amount_paid", None)
    await tdb.bookings.update_one({"_id": b["_id"]}, {"$set": {**upd, "updated_at": now_iso()}})
    nb = await tdb.bookings.find_one({"_id": b["_id"]})
    text = f"Booking {b.get('reference')} updated" + (f": moved to {fmt_date(nb['date'])} {nb['slot']}" if moved else "")
    await add_event(b["lead_id"], "booking", text)
    await audit("booking.edit", text)
    if body.notify_customer:
        await _notify(nb, "updated")
    return {"ok": True, "moved": moved}
