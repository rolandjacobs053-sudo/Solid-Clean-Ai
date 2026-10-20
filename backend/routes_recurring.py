import asyncio
import calendar
import logging
import os
import secrets
from datetime import date, timedelta

import stripe
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel

from comms import add_event, log_comm
from core import audit, company_name, current_company, db, get_settings, now, now_iso, oid, out, require_owner, set_tenant, tdb
from pricing import fmt_date

logger = logging.getLogger(__name__)
cron = APIRouter(prefix="/api/cron")
admin = APIRouter(prefix="/api/admin/recurring", dependencies=[Depends(require_owner)])
DAYS = {"weekly": 7, "fortnightly": 14}
CHARGE_DAYS_BEFORE = 2


def next_visit(d: str, frequency: str, anchor_day: int = 0) -> str:
    cur = date.fromisoformat(d)
    if frequency in DAYS:
        return (cur + timedelta(days=DAYS[frequency])).isoformat()
    m = cur.month % 12 + 1
    y = cur.year + (cur.month == 12)
    return date(y, m, min(anchor_day or cur.day, calendar.monthrange(y, m)[1])).isoformat()


async def start_plan(b: dict):
    try:
        sess = await asyncio.to_thread(stripe.checkout.Session.retrieve, b["session_id"], expand=["payment_intent"])
        pm, customer = sess.payment_intent.payment_method, sess.customer
    except Exception:
        logger.exception("could not read saved card")
        pm = customer = None
    keep = ("lead_id", "quote_id", "customer", "postcode", "address", "service", "service_name", "input", "lines", "total", "slot", "access", "access_notes", "source", "frequency", "residential")
    anchor = date.fromisoformat(b["date"]).day
    plan = {**{k: b.get(k) for k in keep}, "first_booking_id": str(b["_id"]), "anchor_day": anchor, "next_date": next_visit(b["date"], b["frequency"], anchor),
            "stripe_customer": customer, "payment_method": pm, "status": "active" if pm else "needs_card", "created_at": now_iso()}
    pid = str((await tdb.recurring_plans.insert_one(plan)).inserted_id)
    await tdb.bookings.update_one({"_id": b["_id"]}, {"$set": {"recurring_plan_id": pid}})
    await add_event(b["lead_id"], "booking", f"Regular {b['frequency']} clean set up - next visit {fmt_date(plan['next_date'])}"
                    + ("" if pm else " (card not saved - arrange payment manually)"))


async def _charge_visit(plan: dict, s: dict):
    try:
        await _create_and_charge(plan, s)
    finally:
        await tdb.recurring_plans.update_one({"_id": plan["_id"], "next_date": plan["next_date"]},
                                             {"$set": {"next_date": next_visit(plan["next_date"], plan["frequency"], plan.get("anchor_day", 0)), "last_run_at": now_iso()}})


async def _create_and_charge(plan: dict, s: dict):
    from routes_public import finalize_booking, notify_owner
    when = plan["next_date"]
    if await tdb.bookings.find_one({"recurring_plan_id": str(plan["_id"]), "date": when}):
        return
    b = {**{k: plan.get(k) for k in ("lead_id", "quote_id", "customer", "postcode", "address", "service", "service_name", "input", "lines", "total", "slot", "access", "access_notes", "source", "frequency", "residential")},
         "recurring": False, "recurring_plan_id": str(plan["_id"]), "date": when, "deposit_amount": plan["total"], "balance_due": 0, "tip": 0, "payment_mode": "full_upfront",
         "status": "pending_payment", "payment_status": "pending", "accepted_policies": {}, "created_at": now_iso(),
         "reference": f"{current_company.get()['slug'][:2].upper()}-{now().strftime('%y%m')}-{secrets.token_hex(3).upper()}"}
    bid = str((await tdb.bookings.insert_one(b)).inserted_id)
    c = b["customer"]
    try:
        pi = await asyncio.to_thread(stripe.PaymentIntent.create, amount=int(round(plan["total"] * 100)), currency="gbp", customer=plan["stripe_customer"],
                                     payment_method=plan["payment_method"], off_session=True, confirm=True, metadata={"booking_id": bid, "kind": "recurring"},
                                     description=f"{plan['service_name']} - {fmt_date(when)} {plan['slot']}")
        ok = pi.status == "succeeded"
    except stripe.error.StripeError as e:
        logger.warning("recurring charge failed: %s", e)
        ok, pi = False, None
    await tdb.payment_transactions.insert_one({"session_id": pi.id if pi else f"failed-{bid}", "booking_id": bid, "amount": float(plan["total"]), "kind": "recurring", "currency": "gbp",
                                              "status": "complete" if ok else "failed", "payment_status": "paid" if ok else "failed", "created_at": now_iso(), "updated_at": now_iso()})
    if ok:
        try:
            await finalize_booking(bid)
        except Exception:
            logger.exception("finalize failed for recurring visit %s", bid)
            await tdb.bookings.update_one({"_id": oid(bid)}, {"$set": {"status": "confirmed", "payment_status": "paid", "paid_at": now_iso()}})
            await notify_owner(s, f"Regular clean paid - please check booking ({c['name']})",
                               f"£{plan['total']:.2f} was charged for {fmt_date(when)} {plan['slot']} and the visit is confirmed, but the confirmation emails could not be sent. Please contact the customer.", plan["lead_id"])
    else:
        await tdb.bookings.update_one({"_id": oid(bid)}, {"$set": {"status": "payment_failed", "payment_status": "failed"}})
        await log_comm(c["email"], "email", "recurring_payment_failed", "We couldn't take payment for your next clean",
                       f"Hi {c['name']}, we couldn't take the £{plan['total']:.2f} payment for your {plan['service_name']} on {fmt_date(when)} at {plan['slot']}. "
                       f"Please contact {company_name()} to update your card so we can keep your regular clean.", lead_id=plan["lead_id"])
        await notify_owner(s, f"Regular clean payment failed - {c['name']}", f"The automatic payment of £{plan['total']:.2f} for {fmt_date(when)} {plan['slot']} failed. The visit is not confirmed.", plan["lead_id"])
    await tdb.recurring_plans.update_one({"_id": plan["_id"]}, {"$set": {"last_result": "paid" if ok else "failed"}})


async def run_recurring():
    async for company in db.companies.find({}):
        set_tenant(company)
        s = await get_settings()
        due = (now().date() + timedelta(days=CHARGE_DAYS_BEFORE)).isoformat()
        async for plan in tdb.recurring_plans.find({"status": "active", "next_date": {"$lte": due}}):
            try:
                await _charge_visit(plan, s)
            except Exception:
                logger.exception("recurring plan %s failed", plan["_id"])


@cron.post("/recurring")
async def recurring_cron(request: Request, background: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or not secrets.compare_digest(auth[7:], os.environ["WEBHOOK_CRON_SECRET"]):
        raise HTTPException(401, "Unauthorized")
    run_id = request.headers.get("x-webhook-id") or secrets.token_hex(8)
    if (await db.cron_runs.update_one({"_id": run_id}, {"$setOnInsert": {"at": now_iso(), "name": "recurring"}}, upsert=True)).upserted_id is None:
        return {"ok": True, "duplicate": True}
    background.add_task(run_recurring)
    return {"ok": True}


@admin.get("")
async def list_plans():
    plans = await tdb.recurring_plans.find({}, {"stripe_customer": 0}).sort("next_date", 1).to_list(500)
    stats = {}
    async for b in tdb.bookings.find({"recurring_plan_id": {"$in": [str(p["_id"]) for p in plans]}}, {"recurring_plan_id": 1, "date": 1, "status": 1, "payment_status": 1}).sort("date", 1):
        s = stats.setdefault(b["recurring_plan_id"], {"visits": 0, "last_visit": None})
        s["visits"] += 1
        s["last_visit"] = {"date": b["date"], "status": b["status"], "payment_status": b["payment_status"]}
    rows = []
    for p in plans:
        card = bool(p.pop("payment_method", None))
        rows.append({**out(p), "card_saved": card, **stats.get(str(p["_id"]), {"visits": 0, "last_visit": None})})
    return rows


@admin.get("/{plan_id}")
async def get_plan(plan_id: str):
    p = await tdb.recurring_plans.find_one({"_id": oid(plan_id)}, {"stripe_customer": 0, "payment_method": 0})
    if not p:
        raise HTTPException(404, "Plan not found")
    return out(p)


class PlanStatus(BaseModel):
    status: str


@admin.post("/{plan_id}/status")
async def set_plan_status(plan_id: str, body: PlanStatus):
    if body.status not in ("active", "paused", "cancelled"):
        raise HTTPException(422, "Status must be active, paused or cancelled")
    p = await tdb.recurring_plans.find_one({"_id": oid(plan_id)})
    if not p or p["status"] == "cancelled":
        raise HTTPException(400, "This regular clean can't be changed")
    if body.status == "active" and not p.get("payment_method"):
        raise HTTPException(400, "No saved card for this customer")
    nxt = p["next_date"]
    while body.status == "active" and nxt <= now().date().isoformat():
        nxt = next_visit(nxt, p["frequency"], p.get("anchor_day", 0))
    await tdb.recurring_plans.update_one({"_id": p["_id"]}, {"$set": {"status": body.status, "next_date": nxt, "updated_at": now_iso()}})
    await add_event(p["lead_id"], "booking", f"Regular {p['frequency']} clean {body.status}")
    await audit("recurring.status", f"{p['customer']['name']} {body.status}")
    return {"ok": True}
