from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai import ai_complete
from automations import run_automations
from comms import add_event, log_comm
from core import audit, company_name, current_actor, days_ago_iso, get_settings, now, now_iso, oid, out, outs, require_admin, require_owner, tdb
from pricing import fmt_date

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])
CHANNELS = ["google_ads", "seo", "website", "ai_chat", "phone", "cold_email", "referral", "whatsapp", "other"]
LEAD_STATUSES = {"new", "quoted", "booked", "completed", "lost"}


class LeadPatch(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    follow_up_date: Optional[str] = None
    type: Optional[str] = None


class LeadIn(BaseModel):
    name: str
    phone: str = ""
    email: str = ""
    postcode: str = ""
    source: str = "phone"
    type: str = "residential"
    notes: str = ""


class BookingPatch(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None


class SettingsIn(BaseModel):
    business: Dict[str, Any]
    pricing: Dict[str, Any]
    availability: Dict[str, Any]
    knowledge_base: List[Dict[str, str]]


def _ratio(a, b):
    return round(a / b, 2) if b else None


@router.get("/overview")
async def overview(days: int = 30):
    since = days_ago_iso(days) if days > 0 else ""
    today = now().date().isoformat()
    leads = await tdb.leads.find({"created_at": {"$gte": since}}, {"timeline": 0}).to_list(5000)
    paid = await tdb.bookings.find({"created_at": {"$gte": since}, "payment_status": "paid"}).to_list(5000)
    spend = await tdb.spend.find({"month": {"$gte": since[:7]}}).to_list(2000)
    per = {c: {"channel": c, "leads": 0, "bookings": 0, "revenue": 0.0, "spend": 0.0} for c in CHANNELS}
    for l in leads:
        per[l.get("source") if l.get("source") in per else "other"]["leads"] += 1
    for b in paid:
        row = per[b.get("source") if b.get("source") in per else "other"]
        row["bookings"] += 1
        row["revenue"] += b["total"]
    for x in spend:
        per[x["channel"] if x["channel"] in per else "other"]["spend"] += x["amount"]
    channels = []
    for row in per.values():
        row.update(cpl=_ratio(row["spend"], row["leads"]), cac=_ratio(row["spend"], row["bookings"]),
                   roas=_ratio(row["revenue"], row["spend"]), profit=round(row["revenue"] - row["spend"], 2))
        channels.append(row)
    total_spend = sum(r["spend"] for r in channels)
    revenue = sum(b["total"] for b in paid)
    converted = len([l for l in leads if l.get("status") in ("booked", "completed")])
    completed = [b for b in paid if b["status"] == "completed"]
    customers = {}
    async for b in tdb.bookings.find({"payment_status": "paid"}, {"lead_id": 1}):
        customers[b["lead_id"]] = customers.get(b["lead_id"], 0) + 1
    upcoming = await tdb.bookings.find({"status": "confirmed", "date": {"$gte": today}}).sort([("date", 1), ("slot", 1)]).to_list(8)
    follow_ups = await tdb.leads.find({"follow_up_date": {"$ne": None, "$lte": today}, "status": {"$nin": ["completed", "lost"]}},
                                     {"timeline": 0}).to_list(20)
    escalations = await tdb.conversations.find({"escalated": True, "status": "needs_human"}, {"messages": 0}).to_list(20)
    kpis = {
        "new_leads": len(leads), "uncontacted_leads": len([l for l in leads if l.get("status") == "new"]),
        "quotes_awaiting": await tdb.quotes.count_documents({"status": "sent"}),
        "upcoming_jobs": await tdb.bookings.count_documents({"status": "confirmed", "date": {"$gte": today}}),
        "completed_jobs": len(completed), "bookings": len(paid), "revenue": round(revenue, 2),
        "completed_revenue": round(sum(b["total"] for b in completed), 2),
        "ad_spend": round(per["google_ads"]["spend"], 2), "marketing_spend": round(total_spend, 2),
        "cpl": _ratio(total_spend, len(leads)), "cac": _ratio(total_spend, len(paid)),
        "conversion_rate": round(converted / len(leads) * 100, 1) if leads else 0,
        "repeat_customers": len([c for c in customers.values() if c > 1]),
        "commercial_opportunities": await tdb.prospects.count_documents({"status": {"$in": ["interested", "meeting", "proposal"]}}),
        "follow_ups_due": len(follow_ups) + len(escalations),
    }
    funnel = [{"stage": "Enquiries", "value": len(leads)},
              {"stage": "Quoted", "value": len([l for l in leads if l.get("status") in ("quoted", "booked", "completed")])},
              {"stage": "Booked", "value": converted},
              {"stage": "Completed", "value": len([l for l in leads if l.get("status") == "completed"])}]
    return {"kpis": kpis, "channels": channels, "funnel": funnel, "upcoming": outs(upcoming),
            "follow_ups": outs(follow_ups), "escalations": outs(escalations)}


@router.get("/leads")
async def list_leads(status: str = "", source: str = "", q: str = ""):
    query = {}
    if status:
        query["status"] = status
    if source:
        query["source"] = source
    if q:
        query["$or"] = [{f: {"$regex": q, "$options": "i"}} for f in ("name", "email", "phone", "postcode")]
    return outs(await tdb.leads.find(query, {"timeline": 0}).sort("created_at", -1).to_list(500))


@router.post("/leads")
async def create_lead(body: LeadIn):
    doc = {**body.model_dump(), "email": body.email.lower() or None, "status": "new", "follow_up_date": None, "marketing_consent": False,
           "timeline": [{"at": now_iso(), "type": body.source, "text": "Lead added manually"}], "created_at": now_iso(), "updated_at": now_iso()}
    return {"id": str((await tdb.leads.insert_one(doc)).inserted_id)}


@router.get("/leads/{lead_id}")
async def get_lead(lead_id: str):
    lead = await tdb.leads.find_one({"_id": oid(lead_id)})
    if not lead:
        raise HTTPException(404, "Lead not found")
    return {"lead": out(lead),
            "quotes": outs(await tdb.quotes.find({"lead_id": lead_id}).sort("created_at", -1).to_list(50)),
            "bookings": outs(await tdb.bookings.find({"lead_id": lead_id}).sort("created_at", -1).to_list(50)),
            "conversations": outs(await tdb.conversations.find({"lead_id": lead_id}, {"messages": 0}).to_list(20)),
            "communications": outs(await tdb.communications.find({"lead_id": lead_id}).sort("created_at", -1).to_list(50))}


@router.patch("/leads/{lead_id}")
async def patch_lead(lead_id: str, body: LeadPatch):
    data = body.model_dump(exclude_none=True)
    if "status" in data and data["status"] not in LEAD_STATUSES:
        raise HTTPException(400, "Invalid status")
    await tdb.leads.update_one({"_id": oid(lead_id)}, {"$set": {**data, "updated_at": now_iso()}})
    if "status" in data:
        await add_event(lead_id, "status", f"Status changed to {data['status']}")
    return {"ok": True}


@router.get("/bookings")
async def list_bookings(status: str = "", ctx=Depends(require_admin)):
    query = {"status": status} if status else {"status": {"$nin": ["abandoned"]}}
    if ctx["user"]["role"] == "staff":
        query["assigned_to"] = str(ctx["user"]["_id"])
    return outs(await tdb.bookings.find(query).sort([("date", -1), ("slot", 1)]).to_list(500))


@router.patch("/bookings/{booking_id}")
async def patch_booking(booking_id: str, body: BookingPatch, ctx=Depends(require_admin)):
    b = await tdb.bookings.find_one({"_id": oid(booking_id)})
    if not b:
        raise HTTPException(404, "Booking not found")
    if ctx["user"]["role"] == "staff" and (b.get("assigned_to") != str(ctx["user"]["_id"]) or body.status != "completed" or body.assigned_to is not None):
        raise HTTPException(403, "Staff can only mark their own assigned jobs as completed")
    if body.assigned_to is not None:
        from core import db
        staff = await db.users.find_one({"_id": oid(body.assigned_to), "company_id": b["company_id"]}) if body.assigned_to else None
        await tdb.bookings.update_one({"_id": b["_id"]}, {"$set": {"assigned_to": body.assigned_to or None, "assigned_name": staff["name"] if staff else None}})
        if not body.status:
            return {"ok": True}
    if body.status not in ("completed", "cancelled", "confirmed"):
        raise HTTPException(400, "Invalid status")
    await tdb.bookings.update_one({"_id": b["_id"]}, {"$set": {"status": body.status, "updated_at": now_iso()}})
    await audit("booking.status", f"{b.get('reference') or b['_id']} -> {body.status}")
    c, s = b["customer"], await get_settings()
    when = f"{fmt_date(b['date'])} {b['slot']}"
    if body.status == "completed":
        await tdb.leads.update_one({"_id": oid(b["lead_id"])}, {"$set": {"status": "completed"}})
        await add_event(b["lead_id"], "job", f"Job completed: {b['service_name']} {when}")
        await log_comm(c["email"], "email", "feedback_review_request", "How did we do?",
                       f"Hi {c['name']}, thank you for choosing {company_name()}. We'd value your honest feedback - "
                       f"you can leave a review here: {s['business']['review_link']}. If anything wasn't right, just reply and we'll put it right.",
                       kind="follow_up", lead_id=b["lead_id"])
    elif body.status == "cancelled":
        await add_event(b["lead_id"], "job", f"Booking cancelled: {when}. Any refund must be approved and issued manually in Stripe.")
        await log_comm(c["email"], "email", "booking_cancelled", "Your booking has been cancelled",
                       f"Hi {c['name']}, your booking for {when} has been cancelled. We'll be in touch about any refund in line with our cancellation policy.",
                       lead_id=b["lead_id"])
        await tdb.communications.update_many({"lead_id": b["lead_id"], "status": "scheduled", "template": "appointment_reminder"},
                                            {"$set": {"status": "cancelled"}})
    return {"ok": True}


@router.get("/conversations")
async def list_conversations():
    convs = await tdb.conversations.find({}).sort("updated_at", -1).to_list(200)
    for c in convs:
        c["message_count"] = len(c.get("messages", []))
        c["last_message"] = next((m["text"] for m in reversed(c.get("messages", [])) if m["role"] == "user"), "")
        c.pop("messages", None)
    return outs(convs)


@router.get("/conversations/{cid}")
async def get_conversation(cid: str):
    conv = await tdb.conversations.find_one({"_id": oid(cid)})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return {"conversation": out(conv), "quotes": outs(await tdb.quotes.find({"conversation_id": cid}).to_list(20))}


@router.post("/conversations/{cid}/summarise")
async def summarise(cid: str):
    conv = await tdb.conversations.find_one({"_id": oid(cid)})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    transcript = "\n".join(f"{m['role']}: {m['text']}" for m in conv["messages"])
    summary = await ai_complete("You summarise customer service conversations for a cleaning company owner. Write 2-3 factual sentences: "
                                "who, what they need, property details, quote given (only if stated), outcome and next action. No invention.", transcript)
    await tdb.conversations.update_one({"_id": conv["_id"]}, {"$set": {"summary": summary}})
    return {"summary": summary}


@router.patch("/conversations/{cid}/resolve")
async def resolve(cid: str):
    await tdb.conversations.update_one({"_id": oid(cid)}, {"$set": {"status": "resolved"}})
    return {"ok": True}


@router.get("/comms")
async def list_comms(template: str = ""):
    query = {"template": template} if template else {}
    return outs(await tdb.communications.find(query).sort("created_at", -1).to_list(500))


@router.post("/automations/run")
async def automations_run():
    return await run_automations()


@router.get("/settings")
async def read_settings():
    return await get_settings()


def _diff(a, b, path):
    if isinstance(a, dict) and isinstance(b, dict):
        return [c for k in sorted(set(a) | set(b)) for c in _diff(a.get(k), b.get(k), f"{path}.{k}")]
    if isinstance(a, list) and isinstance(b, list) and a + b and all(isinstance(x, dict) and "key" in x for x in a + b):
        am, bm = {x["key"]: x for x in a}, {x["key"]: x for x in b}
        return [c for k in sorted(set(am) | set(bm)) for c in _diff(am.get(k), bm.get(k), f"{path}[{k}]")]
    return [] if a == b else [{"field": path, "old": a, "new": b}]


@router.put("/settings", dependencies=[Depends(require_owner)])
async def write_settings(body: SettingsIn):
    old = await get_settings()
    changes = _diff(old.get("pricing", {}), body.pricing, "pricing")
    if changes:
        await tdb.price_history.insert_one({"at": now_iso(), "actor": current_actor.get(), "changes": changes[:300]})
    await tdb.settings.update_one({}, {"$set": body.model_dump()})
    await audit("settings.update", f"{len(changes)} pricing change(s)")
    return {"ok": True, "pricing_changes": len(changes)}


@router.get("/price-history")
async def price_history():
    return outs(await tdb.price_history.find({}).sort("at", -1).to_list(100))


@router.get("/audit-log", dependencies=[Depends(require_owner)])
async def audit_log():
    return outs(await tdb.audit_logs.find({}).sort("at", -1).to_list(300))



@router.delete("/demo-data")
async def clear_demo():
    removed = 0
    for col in ("leads", "quotes", "bookings", "conversations", "prospects", "reviews", "spend", "communications"):
        removed += (await tdb[col].delete_many({"demo": True})).deleted_count
    return {"removed": removed}
