from datetime import timedelta

from comms import deliver_email, log_comm
from core import db, get_settings, now, now_iso, oid, set_tenant, tdb


async def run_automations() -> dict:
    s = await get_settings()
    biz = s["business"]
    await tdb.photos.update_many({"status": "pending", "is_deleted": False, "created_at": {"$lt": (now() - timedelta(hours=24)).isoformat()}},
                                 {"$set": {"is_deleted": True, "deleted_reason": "never attached to a booking"}})
    cutoff = (now() - timedelta(hours=biz["follow_up_after_hours"])).isoformat()
    follow_ups = 0
    async for q in tdb.quotes.find({"status": "sent", "created_at": {"$lte": cutoff},
                                   "follow_ups_sent": {"$lt": biz["max_follow_ups"]}, "lead_id": {"$ne": None}}):
        lead = await tdb.leads.find_one({"_id": oid(q["lead_id"])})
        if not lead or not lead.get("email") or lead["status"] not in ("new", "quoted"):
            continue
        last = q.get("last_follow_up_at")
        if last and last > cutoff:
            continue
        status = await log_comm(lead["email"], "email", "quote_follow_up", "Still looking for a cleaner?",
                                f"Hi {lead['name']}, just checking whether you had any questions about your {q['service_name']} quote "
                                f"(£{q['total']:.2f}). Reply to this email or book online any time.", kind="follow_up", lead_id=q["lead_id"])
        await tdb.quotes.update_one({"_id": q["_id"]}, {"$inc": {"follow_ups_sent": 1}, "$set": {"last_follow_up_at": now_iso()}})
        follow_ups += status == "sent"
    due = 0
    async for c in tdb.communications.find({"status": "scheduled", "scheduled_for": {"$lte": now_iso()}}):
        status = await deliver_email(c["to"], c["subject"], c["body"], c.get("link")) if c["channel"] == "email" else "simulated"
        await tdb.communications.update_one({"_id": c["_id"]}, {"$set": {"status": status, "sent_at": now_iso()}})
        due += 1
    return {"quote_follow_ups_sent": follow_ups, "scheduled_messages_sent": due, "ran_at": now_iso()}


async def run_all_companies() -> int:
    count = 0
    async for company in db.companies.find({"suspended": {"$ne": True}}):
        set_tenant(company)
        await run_automations()
        count += 1
    return count
