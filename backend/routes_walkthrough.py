from datetime import date, timedelta
from typing import Dict, List, Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from comms import add_event, log_comm, upsert_lead
from core import audit, company_name, get_settings, now, now_iso, oid, out, outs, require_owner, tdb
from pricing import fmt_date
from routes_public import EMAIL_RE, PhotoRef, notify_owner, tenant_from_slug
from storage import attach_photos

public = APIRouter(prefix="/api/public/{slug}/walkthroughs", dependencies=[Depends(tenant_from_slug)])
admin = APIRouter(prefix="/api/admin/walkthroughs", dependencies=[Depends(require_owner)])
TYPES = {"office": "Office", "pub": "Pub", "restaurant": "Restaurant / café", "gym": "Gym / fitness centre", "retail": "Retail shop", "school": "School / educational premises",
         "medical": "Medical / healthcare premises", "warehouse": "Warehouse / industrial premises", "communal": "Communal areas", "other": "Other commercial premises"}
STATUSES = {"requested", "confirmed", "alternative_proposed", "completed", "declined"}


class Contact(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=6, max_length=30)
    email: str = Field(pattern=EMAIL_RE)


class Visit(BaseModel):
    preferred_date: str
    preferred_time: str = Field(min_length=1, max_length=20)
    alt_date: str = ""
    alt_time: str = Field("", max_length=20)
    access_info: str = Field("", max_length=1000)


class Schedule(BaseModel):
    kind: Literal["one_off", "ongoing"]
    frequency: str = Field("", max_length=60)
    days: List[str] = Field([], max_length=7)
    time: str = Field("", max_length=60)
    start_date: str = Field("", max_length=20)
    notes: str = Field("", max_length=1000)


class WalkthroughIn(BaseModel):
    establishment: str
    business_name: str = Field(min_length=1, max_length=160)
    contact: Contact
    address: str = Field(min_length=5, max_length=250)
    postcode: str = Field(min_length=2, max_length=10)
    details: Dict[str, Union[str, int, bool, List[str]]] = Field({}, max_length=40)
    schedule: Schedule
    visit: Visit
    photos: List[PhotoRef] = Field([], max_length=10)
    marketing_consent: bool = False


def _availability_note(av: dict, day: str, alt: str = "") -> str:
    try:
        d = date.fromisoformat(day)
        a = date.fromisoformat(alt) if alt else None
    except ValueError:
        raise HTTPException(422, "Please choose a valid preferred date.")
    if d <= now().date() or (a and a <= now().date()):
        raise HTTPException(422, "Please choose dates in the future.")
    if d.weekday() not in av["working_days"] or day in av["blocked_dates"]:
        return "Outside normal working days - check before confirming"
    return "Within normal working days - not yet confirmed"


@public.post("")
async def request_walkthrough(body: WalkthroughIn):
    if body.establishment not in TYPES:
        raise HTTPException(422, "Please choose the type of premises.")
    for k, v in body.details.items():
        if len(k) > 60 or len(str(v)) > 1000:
            raise HTTPException(422, "One of the answers is too long.")
    s = await get_settings()
    note = _availability_note(s["availability"], body.visit.preferred_date, body.visit.alt_date)
    since = (now() - timedelta(hours=24)).isoformat()
    if await tdb.walkthroughs.count_documents({"contact.email": body.contact.email, "created_at": {"$gte": since}}) >= 3:
        raise HTTPException(429, "We've already received your requests today - our team will be in touch. You can also call us.")
    lead_id = await upsert_lead({**body.contact.model_dump(), "postcode": body.postcode}, "website",
                                f"Free site walkthrough requested: {TYPES[body.establishment]} - {body.business_name}",
                                {"type": "commercial", "marketing_consent": body.marketing_consent})
    doc = {**body.model_dump(exclude={"photos"}), "establishment_name": TYPES[body.establishment], "postcode": body.postcode.upper(),
           "status": "requested", "availability_note": note, "lead_id": lead_id, "history": [{"at": now_iso(), "text": "Request received"}], "created_at": now_iso()}
    wid = str((await tdb.walkthroughs.insert_one(doc)).inserted_id)
    await attach_photos(body.photos, walkthrough_id=wid, lead_id=lead_id)
    when = f"{fmt_date(body.visit.preferred_date)} {body.visit.preferred_time}"
    await notify_owner(s, f"Site walkthrough request - {body.business_name}",
                       f"{body.contact.name} ({body.contact.phone}, {body.contact.email}) requested a free site walkthrough for {TYPES[body.establishment]} "
                       f"at {body.address}, {body.postcode.upper()}. Preferred: {when}. {note}. Review it in the dashboard under Site walkthroughs.", lead_id)
    await log_comm(body.contact.email, "email", "walkthrough_ack", "We've received your site walkthrough request",
                   f"Hi {body.contact.name},\n\nThank you for contacting {company_name()}. We have received your request for a free commercial cleaning site walkthrough "
                   f"(your preferred time: {when}). Our team will review your details and contact you to confirm a suitable date and time. "
                   "The walkthrough is free and there is no obligation to proceed.", lead_id=lead_id)
    return {"ok": True, "id": wid}


class WalkPatch(BaseModel):
    status: Optional[str] = None
    confirmed_date: str = ""
    confirmed_time: str = Field("", max_length=20)
    message: str = Field("", max_length=1500)
    notes: Optional[str] = Field(None, max_length=3000)


@admin.get("")
async def list_walkthroughs():
    return outs(await tdb.walkthroughs.find().sort("created_at", -1).to_list(300))


@admin.get("/{wid}")
async def get_walkthrough(wid: str):
    w = await tdb.walkthroughs.find_one({"_id": oid(wid)})
    if not w:
        raise HTTPException(404, "Request not found")
    photos = await tdb.photos.find({"walkthrough_id": wid, "status": "attached", "is_deleted": False}, {"token": 0, "path": 0}).to_list(20)
    return {"walkthrough": out(w), "photos": outs(photos)}


@admin.patch("/{wid}")
async def update_walkthrough(wid: str, body: WalkPatch):
    w = await tdb.walkthroughs.find_one({"_id": oid(wid)})
    if not w:
        raise HTTPException(404, "Request not found")
    upd = {"updated_at": now_iso()}
    if body.notes is not None:
        upd["notes"] = body.notes
    text = None
    if body.status:
        if body.status not in STATUSES:
            raise HTTPException(400, "Invalid status")
        upd["status"] = body.status
        if w["status"] in ("completed", "declined"):
            raise HTTPException(400, f"This request is already {w['status']}")
        c = w["contact"]
        if body.status == "confirmed":
            if not (body.confirmed_date and body.confirmed_time):
                raise HTTPException(422, "Choose the confirmed date and time")
            try:
                if date.fromisoformat(body.confirmed_date) < now().date():
                    raise HTTPException(422, "The confirmed date is in the past")
            except ValueError:
                raise HTTPException(422, "Choose a valid confirmed date")
            upd.update(confirmed_date=body.confirmed_date, confirmed_time=body.confirmed_time)
            text = f"Visit confirmed for {fmt_date(body.confirmed_date)} {body.confirmed_time}"
            await log_comm(c["email"], "email", "walkthrough_confirmed", f"Your free site walkthrough is confirmed - {fmt_date(body.confirmed_date)} {body.confirmed_time}",
                           f"Hi {c['name']},\n\nYour free, no-obligation site walkthrough at {w['address']} is confirmed for {fmt_date(body.confirmed_date)} at {body.confirmed_time}. "
                           f"{body.message}\n\nKind regards,\n{company_name()}", lead_id=w["lead_id"])
        elif body.status == "alternative_proposed":
            if not body.message.strip():
                raise HTTPException(422, "Add a message with the alternative date and time")
            text = f"Alternative proposed: {body.message[:200]}"
            await log_comm(c["email"], "email", "walkthrough_alternative", "Your site walkthrough - alternative time",
                           f"Hi {c['name']},\n\nThank you for your request. {body.message}\n\nPlease reply to this email or call us to agree a time.\n\nKind regards,\n{company_name()}", lead_id=w["lead_id"])
        else:
            text = f"Status changed to {body.status}"
    push = {"$push": {"history": {"at": now_iso(), "text": text}}} if text else {}
    await tdb.walkthroughs.update_one({"_id": w["_id"]}, {"$set": upd, **push})
    if text:
        await add_event(w["lead_id"], "walkthrough", text)
        await audit("walkthrough.status", f"{w['business_name']}: {text}")
    return {"ok": True}
