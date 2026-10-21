from datetime import date, timedelta
from zoneinfo import ZoneInfo

from core import current_company, db, now, tdb

LIVE = {"demo": {"$ne": True}}
DONE = ("confirmed", "completed")
COST_KEYS = ("cleaner_pay", "supplies", "travel")


def month_bounds(ym: str):
    y, m = int(ym[:4]), int(ym[5:7])
    end = date(y + (m == 12), m % 12 + 1, 1)
    return f"{ym}-01", end.isoformat()


def job_cost(b: dict):
    c = b.get("job_costs")
    return round(sum(float(c.get(k) or 0) for k in COST_KEYS), 2) if c else None


async def month_metrics(ym: str, include_demo: bool = False) -> dict:
    start, end = month_bounds(ym)
    base = {} if include_demo else LIVE
    jobs = await tdb.bookings.find({**base, "date": {"$gte": start, "$lt": end}, "status": {"$in": list(DONE)},
                                     "payment_status": {"$in": ["paid", "deposit_paid"]}}, {"timeline": 0}).to_list(5000)
    leads = await tdb.leads.count_documents({**base, "created_at": {"$gte": start, "$lt": end}})
    expenses = await tdb.expenses.find({"date": {"$gte": start, "$lt": end}}).to_list(5000)
    spend = await tdb.spend.find({**base, "month": ym}).to_list(500)
    revenue = round(sum(float(b.get("total") or 0) for b in jobs), 2)
    costed = [b for b in jobs if job_cost(b) is not None]
    job_costs = round(sum(job_cost(b) for b in costed), 2)
    exp_total = round(sum(float(e["amount"]) for e in expenses), 2)
    mkt = round(sum(float(x["amount"]) for x in spend), 2)
    by_service = {}
    for b in jobs:
        r = by_service.setdefault(b.get("service_name") or b.get("service"), {"jobs": 0, "revenue": 0.0, "costed_jobs": 0, "costed_revenue": 0.0, "job_costs": 0.0})
        r["jobs"] += 1
        r["revenue"] += float(b.get("total") or 0)
        if job_cost(b) is not None:
            r["costed_jobs"] += 1
            r["costed_revenue"] += float(b.get("total") or 0)
            r["job_costs"] += job_cost(b)
    for r in by_service.values():
        r["gross_profit_on_costed_jobs"] = round(r["costed_revenue"] - r["job_costs"], 2) if r["costed_jobs"] else None
        r["margin_pct"] = round(r["gross_profit_on_costed_jobs"] / r["costed_revenue"] * 100, 1) if r["costed_jobs"] and r["costed_revenue"] else None
        r["revenue"] = round(r["revenue"], 2)
    missing = len(jobs) - len(costed)
    return {
        "month": ym, "jobs_booked_or_done": len(jobs), "jobs_completed": len([b for b in jobs if b["status"] == "completed"]),
        "revenue": revenue, "enquiries": leads, "average_job_value": round(revenue / len(jobs), 2) if jobs else None,
        "job_costs_recorded": job_costs, "jobs_missing_costs": missing, "expenses_recorded": exp_total, "marketing_spend": mkt,
        "profit": round(revenue - job_costs - exp_total - mkt, 2),
        "profit_status": "actual" if jobs and not missing else ("incomplete - some job costs not recorded" if jobs else "no jobs"),
        "expenses_by_category": _group(expenses), "by_service": by_service,
    }


def _group(expenses):
    out = {}
    for e in expenses:
        out[e["category"]] = round(out.get(e["category"], 0) + float(e["amount"]), 2)
    return out


def _count(docs):
    out = {}
    for d in docs:
        out[d.get("status") or "unknown"] = out.get(d.get("status") or "unknown", 0) + 1
    return out


async def snapshot() -> dict:
    today = now().astimezone(ZoneInfo("Europe/London")).date()
    ym = today.strftime("%Y-%m")
    last = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    in14 = (today + timedelta(days=14)).isoformat()
    t = today.isoformat()
    upcoming = await tdb.bookings.find({**LIVE, "status": "confirmed", "date": {"$gte": t, "$lte": in14}}, {"timeline": 0}).sort([("date", 1)]).to_list(100)
    outstanding = await tdb.bookings.find({**LIVE, "status": {"$in": ["confirmed", "completed", "pending_payment"]},
                                           "$or": [{"balance_due": {"$gt": 0}}, {"payment_status": {"$in": ["pending", "failed"]}}]}, {"timeline": 0}).to_list(200)
    leads_all = await tdb.leads.find(LIVE, {"timeline": 0}).to_list(5000)
    converted = [l for l in leads_all if l.get("status") in ("booked", "completed")]
    plans = await tdb.recurring_plans.find({**LIVE, "status": {"$in": ["active", "needs_card", "paused"]}}).to_list(500)
    reviews = await tdb.reviews.find(LIVE).to_list(1000)
    approved = [r for r in reviews if r.get("status") in ("approved", "responded")]
    staff = await db.users.count_documents({"company_id": current_company.get()["id"], "role": "staff", "active": {"$ne": False}})
    sources = {}
    for l in leads_all:
        sources[l.get("source") or "other"] = sources.get(l.get("source") or "other", 0) + 1
    return {
        "today": t,
        "data_note": "Figures exclude records tagged as demo. Revenue = value of paid confirmed/completed jobs dated in the month. Profit = revenue - recorded job costs - recorded expenses - recorded marketing spend. Anonymous website price checks are visitors who saw an instant price without leaving contact details - they cannot be followed up.",
        "demo_records_present": await tdb.bookings.count_documents({"demo": True}) + await tdb.leads.count_documents({"demo": True}),
        "this_month": await month_metrics(ym), "last_month": await month_metrics(last),
        "all_time": {"enquiries": len(leads_all), "converted_enquiries": len(converted),
                     "enquiry_to_booking_conversion_pct": round(len(converted) / len(leads_all) * 100, 1) if leads_all else None,
                     "enquiries_by_source": sources,
                     "open_enquiries_not_contacted": len([l for l in leads_all if l.get("status") == "new"])},
        "quotes_sent_to_contactable_enquiries": await tdb.quotes.count_documents({**LIVE, "status": "sent", "lead_id": {"$ne": None}}),
        "anonymous_website_price_checks": await tdb.quotes.count_documents({**LIVE, "lead_id": None}),
        "carpet_quotes_awaiting_admin": await tdb.carpet_quotes.count_documents({**LIVE, "status": "awaiting_review"}),
        "walkthrough_requests_open": await tdb.walkthroughs.count_documents({**LIVE, "status": "requested"}),
        "follow_ups_overdue": await tdb.leads.count_documents({**LIVE, "follow_up_date": {"$ne": None, "$lt": t}, "status": {"$nin": ["completed", "lost"]}}),
        "customer_escalations_open": await tdb.conversations.count_documents({**LIVE, "escalated": True, "status": "needs_human"}),
        "upcoming_jobs_14_days": [{"date": b["date"], "slot": b.get("slot"), "service": b.get("service_name"), "postcode": b.get("postcode"),
                                   "total": b.get("total"), "assigned_to": b.get("assigned_name")} for b in upcoming],
        "upcoming_jobs_unassigned": len([b for b in upcoming if not b.get("assigned_to")]),
        "outstanding_payments": {"count": len(outstanding), "amount": round(sum(float(b.get("balance_due") or (b.get("total") if b.get("payment_status") != "paid" else 0) or 0) for b in outstanding), 2)},
        "recurring_clients": {"active": len([p for p in plans if p["status"] == "active"]), "needs_card": len([p for p in plans if p["status"] == "needs_card"]),
                              "paused": len([p for p in plans if p["status"] == "paused"]),
                              "plans": [{"service": p.get("service_name"), "frequency": p.get("frequency"), "visit_price": p.get("total"), "next_date": p.get("next_date"), "status": p["status"]} for p in plans]},
        "reviews": {"approved_count": len(approved), "average_rating": round(sum(r["rating"] for r in approved) / len(approved), 2) if approved else None,
                    "by_status": _count(reviews)},
        "commercial_prospects_by_status": _count(await tdb.prospects.find(LIVE, {"status": 1}).to_list(5000)),
        "active_staff_accounts": staff,
    }
