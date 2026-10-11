import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ai import ai_complete
from comms import is_suppressed, log_comm
from core import company_name, current_company, feature, get_settings, now_iso, oid, outs, require_admin, tdb

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])
outreach = APIRouter(prefix="/api/admin", dependencies=[Depends(feature("outreach"))])
reviews_r = APIRouter(prefix="/api/admin", dependencies=[Depends(feature("reviews"))])
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SECTORS = ["letting_agent", "estate_agent", "property_management", "landlord", "airbnb_management", "office", "gym", "construction"]
CONSENT_SECTORS = {"landlord"}
REPLY_STATUS = {"interested": "interested", "not_interested": "not_interested", "question": "replied",
                "out_of_office": "contacted", "unsubscribe": "opted_out"}


class ProspectIn(BaseModel):
    company: str = Field(min_length=1)
    sector: str
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    area: str = ""
    website: str = ""
    notes: str = ""
    consent: bool = False


class ProspectPatch(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    deal_value: Optional[float] = None


class SendIn(BaseModel):
    subject: str
    body: str
    origin_url: str


class ReplyIn(BaseModel):
    text: str = Field(min_length=1)


class SuppressIn(BaseModel):
    email: str
    reason: str = "manual"


class ReviewIn(BaseModel):
    author: str
    rating: int = Field(ge=1, le=5)
    text: str = ""
    platform: str = "google"
    review_date: str


class ReviewPatch(BaseModel):
    response: Optional[str] = None
    status: Optional[str] = None


class SpendIn(BaseModel):
    channel: str
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    amount: float = Field(ge=0)
    notes: str = ""


async def _prospect(pid: str):
    p = await tdb.prospects.find_one({"_id": oid(pid)})
    if not p:
        raise HTTPException(404, "Prospect not found")
    return p


@outreach.get("/prospects")
async def list_prospects(sector: str = "", status: str = ""):
    query = {k: v for k, v in {"sector": sector, "status": status}.items() if v}
    return outs(await tdb.prospects.find(query).sort("created_at", -1).to_list(1000))


@outreach.post("/prospects")
async def create_prospect(body: ProspectIn):
    if body.sector not in SECTORS:
        raise HTTPException(400, "Unknown sector")
    email = body.email.lower().strip()
    status = "opted_out" if await is_suppressed(email) else "to_contact"
    doc = {**body.model_dump(), "email": email, "status": status, "steps_sent": 0, "deal_value": None,
           "email_check": "valid_format" if EMAIL_RE.match(email) else ("missing" if not email else "invalid_format"),
           "requires_consent": body.sector in CONSENT_SECTORS, "history": [], "created_at": now_iso()}
    return {"id": str((await tdb.prospects.insert_one(doc)).inserted_id), "status": status}


@outreach.patch("/prospects/{pid}")
async def patch_prospect(pid: str, body: ProspectPatch):
    await tdb.prospects.update_one({"_id": oid(pid)}, {"$set": body.model_dump(exclude_none=True)})
    return {"ok": True}


@outreach.delete("/prospects/{pid}")
async def delete_prospect(pid: str):
    await tdb.prospects.delete_one({"_id": oid(pid)})
    return {"ok": True}


@outreach.post("/prospects/{pid}/draft")
async def draft_email(pid: str):
    p = await _prospect(pid)
    step = p.get("steps_sent", 0) + 1
    text = await ai_complete(
        f"You write short, genuine B2B cold emails for {company_name()}, a cleaning company. "
        "Use only facts given in the notes. "
        "Under 120 words, plain British English, one clear call to action (a 10-minute call). No made-up statistics, clients, prices or claims. "
        "Output exactly:\nSUBJECT: <subject>\n\n<body>",
        f"Write email #{step} of a 3-step sequence{' (a polite follow-up)' if step > 1 else ''} to {p.get('contact_name') or 'the team'} at "
        f"{p['company']} ({p['sector'].replace('_', ' ')}, area: {p.get('area') or 'South London/Surrey'}). Notes: {p.get('notes') or 'none'}.")
    subject, _, body = text.partition("\n")
    return {"subject": subject.replace("SUBJECT:", "").strip(), "body": body.strip(), "step": step}


@outreach.post("/prospects/{pid}/send")
async def send_email(pid: str, body: SendIn):
    p = await _prospect(pid)
    if p["status"] == "opted_out" or await is_suppressed(p["email"]):
        raise HTTPException(409, "This contact has opted out - marketing emails are blocked.")
    if p.get("email_check") != "valid_format":
        raise HTTPException(400, "Email address missing or invalid.")
    if p.get("requires_consent") and not p.get("consent"):
        raise HTTPException(409, "Individual/sole-trader contacts need recorded consent before marketing emails (PECR).")
    footer = f"\n\n--\n{company_name()}. Not interested? Unsubscribe: {body.origin_url.rstrip('/')}/c/{current_company.get()['slug']}/unsubscribe?email={p['email']}"
    await log_comm(p["email"], "email", "cold_outreach", body.subject, body.body + footer, kind="marketing", extra={"prospect_id": pid})
    await tdb.prospects.update_one({"_id": p["_id"]}, {"$inc": {"steps_sent": 1}, "$set": {"status": "contacted", "last_contacted_at": now_iso()},
                                                      "$push": {"history": {"at": now_iso(), "type": "sent", "text": body.subject}}})
    return {"ok": True}


@outreach.post("/prospects/{pid}/classify-reply")
async def classify_reply(pid: str, body: ReplyIn):
    p = await _prospect(pid)
    raw = await ai_complete("Classify a reply to a B2B cleaning-services email. Answer with exactly one word from: "
                            "interested, not_interested, question, out_of_office, unsubscribe.", body.text)
    category = next((c for c in REPLY_STATUS if c in raw.lower()), "question")
    await tdb.prospects.update_one({"_id": p["_id"]}, {"$set": {"status": REPLY_STATUS[category], "last_reply": body.text},
                                                      "$push": {"history": {"at": now_iso(), "type": "reply", "text": f"{category}: {body.text[:200]}"}}})
    if category == "unsubscribe" and p.get("email"):
        await tdb.suppressions.update_one({"email": p["email"]}, {"$setOnInsert": {"reason": "replied_unsubscribe", "created_at": now_iso()}}, upsert=True)
    return {"category": category, "status": REPLY_STATUS[category]}


@outreach.get("/suppressions")
async def list_suppressions():
    return outs(await tdb.suppressions.find({}).sort("created_at", -1).to_list(2000))


@outreach.post("/suppressions")
async def add_suppression(body: SuppressIn):
    email = body.email.lower().strip()
    await tdb.suppressions.update_one({"email": email}, {"$setOnInsert": {"reason": body.reason, "created_at": now_iso()}}, upsert=True)
    await tdb.prospects.update_many({"email": email}, {"$set": {"status": "opted_out"}})
    return {"ok": True}


@reviews_r.get("/reviews")
async def list_reviews():
    reviews = await tdb.reviews.find({}).sort("review_date", -1).to_list(1000)
    by_month = {}
    for r in reviews:
        m = by_month.setdefault(r["review_date"][:7], {"month": r["review_date"][:7], "count": 0, "total": 0})
        m["count"] += 1
        m["total"] += r["rating"]
    trend = [{"month": k, "count": v["count"], "avg": round(v["total"] / v["count"], 2)} for k, v in sorted(by_month.items())]
    avg = round(sum(r["rating"] for r in reviews) / len(reviews), 2) if reviews else None
    return {"reviews": outs(reviews), "stats": {"count": len(reviews), "average": avg, "trend": trend,
                                                "needs_attention": len([r for r in reviews if r.get("status") == "needs_attention"])}}


@reviews_r.post("/reviews")
async def create_review(body: ReviewIn):
    status = "needs_attention" if body.rating <= 3 else "new"
    doc = {**body.model_dump(), "status": status, "response": "", "created_at": now_iso()}
    rid = str((await tdb.reviews.insert_one(doc)).inserted_id)
    if status == "needs_attention":
        s = await get_settings()
        await log_comm(s["business"]["owner_notify_email"], "email", "owner_notification", f"{body.rating}-star review needs attention",
                       f"{body.author}: {body.text}")
    return {"id": rid}


@reviews_r.post("/reviews/{rid}/draft")
async def draft_review_reply(rid: str):
    r = await tdb.reviews.find_one({"_id": oid(rid)})
    if not r:
        raise HTTPException(404, "Review not found")
    text = await ai_complete(f"You draft public replies to customer reviews for {company_name()}, a cleaning company. Be sincere, professional, "
                             "under 80 words, thank the reviewer by first name. For negative reviews apologise, don't argue, and invite them to contact us "
                             "directly. Never offer compensation or admit liability. Output only the reply.",
                             f"{r['rating']}-star review by {r['author']}: {r['text']}")
    await tdb.reviews.update_one({"_id": r["_id"]}, {"$set": {"response": text, "status": "draft_ready"}})
    return {"response": text}


@reviews_r.patch("/reviews/{rid}")
async def patch_review(rid: str, body: ReviewPatch):
    await tdb.reviews.update_one({"_id": oid(rid)}, {"$set": body.model_dump(exclude_none=True)})
    return {"ok": True}


@router.get("/spend")
async def list_spend():
    return outs(await tdb.spend.find({}).sort("month", -1).to_list(1000))


@router.post("/spend")
async def add_spend(body: SpendIn):
    return {"id": str((await tdb.spend.insert_one({**body.model_dump(), "created_at": now_iso()})).inserted_id)}


@router.delete("/spend/{sid}")
async def delete_spend(sid: str):
    await tdb.spend.delete_one({"_id": oid(sid)})
    return {"ok": True}
