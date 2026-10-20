from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

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


class RefundIn(BaseModel):
    amount: float = Field(ge=0)
    note: str = Field("", max_length=500)


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
            "photos": outs(await tdb.photos.find({"lead_id": lead_id, "status": "attached", "is_deleted": False}, {"token": 0, "path": 0}).to_list(50)),
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
async def list_bookings(status: str = "", date_from: str = "", date_to: str = "", ctx=Depends(require_admin)):
    query = {"status": status} if status else {"status": {"$nin": ["abandoned"]}}
    if date_from and date_to:
        query["date"] = {"$gte": date_from, "$lte": date_to}
    if ctx["user"]["role"] == "staff":
        query["assigned_to"] = str(ctx["user"]["_id"])
    return outs(await tdb.bookings.find(query).sort([("date", -1), ("slot", 1)]).to_list(500))


@router.post("/bookings/{booking_id}/balance-link", dependencies=[Depends(require_owner)])
async def balance_link(booking_id: str, request: Request):
    import stripe
    from comms import booking_link
    b = await tdb.bookings.find_one({"_id": oid(booking_id)})
    if not b or b.get("payment_status") != "deposit_paid" or not b.get("balance_due"):
        raise HTTPException(400, "There is no outstanding balance on this booking")
    origin = booking_link(request, "x", "x")[1].split("/c/")[0]
    session = stripe.checkout.Session.create(
        mode="payment", customer_email=b["customer"]["email"], metadata={"booking_id": booking_id, "kind": "balance"},
        line_items=[{"quantity": 1, "price_data": {"currency": "gbp", "unit_amount": int(round(b["balance_due"] * 100)), "tax_behavior": "inclusive",
                     "product_data": {"name": f"Balance - {b['service_name']} {fmt_date(b['date'])} (ref {b.get('reference')})"}}}],
        success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}", cancel_url=f"{origin}/")
    await tdb.payment_transactions.insert_one({"session_id": session.id, "booking_id": booking_id, "amount": float(b["balance_due"]), "kind": "balance",
                                              "currency": "gbp", "status": "initiated", "payment_status": "pending", "created_at": now_iso(), "updated_at": now_iso()})
    status = await log_comm(b["customer"]["email"], "email", "balance_request", f"Balance due - {b['service_name']} (ref {b.get('reference')})",
                            f"Hi {b['customer']['name']}, thank you for choosing {company_name()}. The remaining balance of £{b['balance_due']:.2f} for your "
                            f"{b['service_name']} on {fmt_date(b['date'])} is now due. Please use the secure Stripe button below to pay.",
                            lead_id=b["lead_id"], link=("Pay balance securely", session.url))
    await audit("booking.balance_link", b.get("reference") or booking_id)
    return {"url": session.url, "email_status": status}


def refund_rule(b: dict) -> dict:
    start = datetime.fromisoformat(f"{b['date']}T{b['slot']}").replace(tzinfo=ZoneInfo("Europe/London"))
    hours = max((start - now()).total_seconds() / 3600, 0)
    pct = 100 if hours >= 168 else 50 if hours >= 48 else 0
    paid = b["deposit_amount"] if b.get("payment_status") == "deposit_paid" else b["total"]
    tip = float(b.get("tip") or 0)
    return {"notice_hours": round(hours, 1), "rule_percent": pct, "service_paid": round(paid, 2), "tip": tip,
            "paid": round(paid + tip, 2), "suggested": round(paid * pct / 100 + tip, 2)}


async def _paid_booking(booking_id: str) -> dict:
    b = await tdb.bookings.find_one({"_id": oid(booking_id)})
    if not b or b.get("status") != "confirmed" or b.get("payment_status") not in ("paid", "deposit_paid"):
        raise HTTPException(400, "Only confirmed, paid bookings can be cancelled with a refund")
    return b


@router.get("/bookings/{booking_id}/refund-quote", dependencies=[Depends(require_owner)])
async def refund_quote(booking_id: str):
    return refund_rule(await _paid_booking(booking_id))


@router.post("/bookings/{booking_id}/cancel-refund", dependencies=[Depends(require_owner)])
async def cancel_refund(booking_id: str, body: RefundIn):
    b = await _paid_booking(booking_id)
    rule = refund_rule(b)
    if body.amount > rule["paid"]:
        raise HTTPException(400, f"The refund can't be more than the £{rule['paid']:.2f} the customer paid")
    refund = {**rule, "amount": round(body.amount, 2), "note": body.note.strip(), "status": "to_issue_in_stripe",
              "recorded_at": now_iso(), "recorded_by": current_actor.get()}
    res = await tdb.bookings.update_one({"_id": b["_id"], "status": "confirmed"}, {"$set": {"status": "cancelled", "refund": refund, "updated_at": now_iso(), **({"payment_status": "refund_due"} if refund["amount"] > 0 else {})}})
    if not res.modified_count:
        raise HTTPException(409, "This booking has already changed - please refresh")
    await _cancel_effects(b, refund)
    await audit("booking.cancel_refund", f"{b.get('reference') or booking_id} refund £{refund['amount']:.2f}")
    return refund


@router.post("/bookings/{booking_id}/tip-request", dependencies=[Depends(require_owner)])
async def tip_request(booking_id: str, request: Request):
    import secrets
    b = await tdb.bookings.find_one({"_id": oid(booking_id)})
    if not b or b.get("status") != "completed":
        raise HTTPException(400, "Tip requests can only be sent for completed jobs")
    token = b.get("tip_token") or secrets.token_urlsafe(16)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    url = f"https://{host}/tip/{booking_id}?t={token}"
    c = b["customer"]
    status = await log_comm(c["email"], "email", "tip_request", f"Happy with your clean? - {company_name()}",
                            f"Hi {c['name']}, thank you for choosing {company_name()}. If you were happy with your {b['service_name']} on {fmt_date(b['date'])}, "
                            "you can leave an optional tip for your cleaning team using the secure link below. Thank you!",
                            lead_id=b["lead_id"], link=("Leave a tip", url))
    await tdb.bookings.update_one({"_id": b["_id"]}, {"$set": {"tip_token": token, "tip_request_sent_at": now_iso()}})
    await add_event(b["lead_id"], "job", f"Tip request sent for booking {b.get('reference')}")
    await audit("booking.tip_request", b.get("reference") or booking_id)
    return {"url": url, "email_status": status}


async def _cancel_effects(b: dict, refund: Optional[dict] = None):
    if b.get("recurring_plan_id"):
        plan = await tdb.recurring_plans.find_one({"_id": oid(b["recurring_plan_id"]), "first_booking_id": str(b["_id"]), "status": {"$ne": "cancelled"}})
        if plan:
            await tdb.recurring_plans.update_one({"_id": plan["_id"]}, {"$set": {"status": "cancelled", "updated_at": now_iso()}})
            await add_event(b["lead_id"], "booking", f"Regular {plan['frequency']} clean cancelled with the first booking")
    c, when = b["customer"], f"{fmt_date(b['date'])} {b['slot']}"
    if refund is None:
        event = f"Booking cancelled: {when}. Any refund must be approved and issued manually in Stripe."
        msg = "We'll be in touch about any refund in line with our cancellation policy."
    else:
        event = (f"Booking cancelled: {when}. Refund recorded: £{refund['amount']:.2f} ({refund['rule_percent']}% rule, "
                 f"{refund['notice_hours']}h notice) - issue it manually in Stripe.")
        msg = (f"In line with our Terms and Conditions, a refund of £{refund['amount']:.2f} will be made to your original payment method." if refund["amount"] > 0
               else "In line with our Terms and Conditions, this cancellation is not eligible for a refund.")
    await add_event(b["lead_id"], "job", event)
    await log_comm(c["email"], "email", "booking_cancelled", "Your booking has been cancelled",
                   f"Hi {c['name']}, your booking for {when} has been cancelled. {msg}", lead_id=b["lead_id"])
    await tdb.communications.update_many({"lead_id": b["lead_id"], "status": "scheduled", "template": "appointment_reminder"},
                                        {"$set": {"status": "cancelled"}})


@router.patch("/bookings/{booking_id}")
async def patch_booking(booking_id: str, body: BookingPatch, request: Request, ctx=Depends(require_admin)):
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
    if body.status == b.get("status"):
        return {"ok": True}
    await tdb.bookings.update_one({"_id": b["_id"]}, {"$set": {"status": body.status, "updated_at": now_iso()}})
    await audit("booking.status", f"{b.get('reference') or b['_id']} -> {body.status}")
    c, s = b["customer"], await get_settings()
    when = f"{fmt_date(b['date'])} {b['slot']}"
    if body.status == "completed":
        await tdb.leads.update_one({"_id": oid(b["lead_id"])}, {"$set": {"status": "completed"}})
        await add_event(b["lead_id"], "job", f"Job completed: {b['service_name']} {when}")
        import secrets
        token = b.get("feedback_token") or secrets.token_urlsafe(16)
        await tdb.bookings.update_one({"_id": b["_id"]}, {"$set": {"feedback_token": token}})
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        await log_comm(c["email"], "email", "feedback_review_request", "How did we do?",
                       f"Hi {c['name']}, thank you for choosing {company_name()}. We'd value your honest feedback on your {b['service_name']} - "
                       "it only takes a minute. If anything wasn't right, just reply and we'll put it right.",
                       kind="follow_up", lead_id=b["lead_id"], link=("Rate your clean", f"https://{host}/feedback/{booking_id}?t={token}"))
    elif body.status == "cancelled":
        await _cancel_effects(b)
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
