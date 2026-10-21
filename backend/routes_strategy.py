import json
import logging
import os
import secrets
from datetime import timedelta
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from ai import ai_complete
from business_data import LIVE, insights, snapshot
from comms import add_event, is_suppressed, log_comm
from core import audit, current_company, db, now, now_iso, oid, out, outs, require_owner, set_tenant, tdb
from routes_knowledge import relevant

router = APIRouter(prefix="/api/admin/strategy", dependencies=[Depends(require_owner)])
cron = APIRouter(prefix="/api/cron")
logger = logging.getLogger(__name__)
METRICS = {"monthly_profit": "Monthly profit (£, this month, actual)", "monthly_revenue": "Monthly revenue (£, this month)", "monthly_jobs": "Paid jobs this month",
           "monthly_enquiries": "Enquiries this month", "active_recurring_clients": "Active regular clients", "commercial_contracts_won": "Commercial prospects won",
           "average_rating": "Average approved review rating", "repeat_customer_pct": "Repeat customers (%)", "annual_revenue_run_rate": "Annual revenue run-rate (£, this month x 12)"}


class GoalIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    metric: str
    target: float = Field(gt=0)
    deadline: str = Field(default="", max_length=10)
    notes: str = Field(default="", max_length=500)


class DraftEdit(BaseModel):
    subject: Optional[str] = Field(default=None, max_length=200)
    body: Optional[str] = Field(default=None, max_length=5000)


class ReportIn(BaseModel):
    kind: Literal["daily", "weekly", "monthly"] = "daily"


def metric_value(snap: dict, metric: str):
    tm = snap["this_month"]
    return {"monthly_profit": tm["profit"], "monthly_revenue": tm["revenue"], "monthly_jobs": tm["jobs_booked_or_done"], "monthly_enquiries": tm["enquiries"],
            "active_recurring_clients": snap["recurring_clients"]["active"], "commercial_contracts_won": snap["commercial_prospects_by_status"].get("won", 0),
            "average_rating": snap["reviews"]["average_rating"] or 0, "repeat_customer_pct": snap["analysis"]["repeat_customer_pct"] or 0,
            "annual_revenue_run_rate": round(tm["revenue"] * 12, 2)}.get(metric)


async def goals_with_progress(snap=None) -> list:
    snap = snap or await snapshot()
    if not await tdb.goals.count_documents({}) and current_company.get().get("comped"):
        for g in ({"title": "£10,000 monthly profit", "metric": "monthly_profit", "target": 10000, "deadline": "", "notes": "Owner's first milestone"},
                  {"title": "£400 million annual revenue (long-term ambition)", "metric": "annual_revenue_run_rate", "target": 400_000_000, "deadline": "", "notes": "Owner's long-term ambition; alternative: £400m valuation"}):
            await tdb.goals.insert_one({**g, "status": "active", "created_at": now_iso()})
    rows = []
    for g in outs(await tdb.goals.find({"status": "active"}).sort("created_at", 1).to_list(50)):
        v = metric_value(snap, g["metric"])
        rows.append({**g, "metric_label": METRICS.get(g["metric"], g["metric"]), "current": v, "progress_pct": round(min(100, max(0, (v or 0) / g["target"] * 100)), 3)})
    return rows


@router.get("/goals")
async def list_goals():
    return {"goals": await goals_with_progress(), "metrics": METRICS}


@router.post("/goals")
async def add_goal(body: GoalIn):
    if body.metric not in METRICS:
        raise HTTPException(400, "Unknown metric")
    return {"id": str((await tdb.goals.insert_one({**body.model_dump(), "status": "active", "created_at": now_iso()})).inserted_id)}


@router.put("/goals/{gid}")
async def edit_goal(gid: str, body: GoalIn):
    if body.metric not in METRICS:
        raise HTTPException(400, "Unknown metric")
    if not (await tdb.goals.update_one({"_id": oid(gid)}, {"$set": body.model_dump()})).matched_count:
        raise HTTPException(404, "Goal not found")
    return {"ok": True}


@router.delete("/goals/{gid}")
async def delete_goal(gid: str):
    if not (await tdb.goals.update_one({"_id": oid(gid)}, {"$set": {"status": "archived"}})).matched_count:
        raise HTTPException(404, "Goal not found")
    return {"ok": True}


@router.get("/insights")
async def get_insights():
    return insights(await snapshot())


ROADMAP = """You are a cleaning-industry strategist, financial analyst and operator building a long-term roadmap for {biz} (UK cleaning company, London & Surrey; services: residential/regular, end of tenancy, carpet, commercial).
Owner's ambition: grow to £400m ANNUAL REVENUE or a £400m VALUATION. First milestone: £10,000 monthly profit.
Use the LIVE DATA for the starting point (never invent current figures; if data is missing say so). Use the KNOWLEDGE lessons as evidence where relevant and cite them by company/source; anything else is your estimate - label it.
Explain revenue vs valuation: valuation is typically a multiple of profit (EBITDA); state the multiple you assume as an assumption and what revenue/EBITDA margin each target implies.
Return ONLY JSON: {{"current_stage": int 1-7, "current_position": "2-3 sentences from actual data", "revenue_vs_valuation": "explanation with the implied numbers and assumptions",
"stages": [7 objects: {{"n": 1-7, "name": "", "goal": "", "timeframe_estimate": "", "annual_revenue": "", "monthly_profit": "", "staff": "", "customers": "", "contracts": "", "investment": "", "systems": ["..."], "key_actions": ["3-5 concrete actions"], "exit_criteria": ["measurable criteria to move to next stage"], "risks": ["..."], "evidence": ["lessons/sources used, or 'estimate'"], "assumptions": ["..."]}}],
"next_90_days": ["5-7 concrete actions ordered by priority"], "biggest_constraints": ["..."]}}
Stages framework (adapt with analysis): 1 profitable reliable operation; 2 predictable acquisition & recurring revenue; 3 team & managers deliver without the owner; 4 London & Surrey density then other UK cities; 5 major commercial contracts & management structure; 6 new locations, acquisitions, partnerships, licensing or franchising; 7 national group & international.

KNOWLEDGE:
{knowledge}

LIVE DATA ({today}):
{data}"""


@router.get("/roadmap")
async def get_roadmap():
    r = await tdb.roadmaps.find_one({}, sort=[("created_at", -1)])
    return out(r) if r else None


async def _job(kind: str, coro):
    await tdb.jobs.update_one({"kind": kind}, {"$set": {"status": "running", "error": None, "started_at": now_iso()}}, upsert=True)
    try:
        res = await coro
        await tdb.jobs.update_one({"kind": kind}, {"$set": {"status": "done", "result_id": res, "finished_at": now_iso()}})
    except Exception:
        logger.exception("%s job failed", kind)
        await tdb.jobs.update_one({"kind": kind}, {"$set": {"status": "failed", "error": "The AI couldn't finish this right now. Please try again.", "finished_at": now_iso()}})


async def _start(kind: str, coro, background: BackgroundTasks):
    stale = (now() - timedelta(minutes=5)).isoformat()
    try:
        await tdb.jobs.update_one({"kind": kind, "$or": [{"status": {"$ne": "running"}}, {"started_at": {"$lt": stale}}]},
                                  {"$set": {"status": "running", "error": None, "started_at": now_iso()}}, upsert=True)
    except DuplicateKeyError:
        coro.close()
        return {"status": "running"}
    background.add_task(_job, kind, coro)
    return {"status": "running"}


@router.get("/jobs/{kind}")
async def job_status(kind: str):
    j = await tdb.jobs.find_one({"kind": kind}, {"_id": 0})
    return j or {"status": "idle"}


async def _roadmap() -> str:
    snap = await snapshot()
    s = await tdb.settings.find_one({}, {"business.name": 1})
    know = await relevant("scaling growth expansion franchising acquisition commercial contracts recurring revenue valuation management team", 14)
    raw = await ai_complete(ROADMAP.format(biz=s["business"]["name"], knowledge=json.dumps(know)[:14000], today=snap["today"], data=json.dumps(snap, default=str)[:16000]), "Build the roadmap.")
    plan = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    assert len(plan["stages"]) >= 5
    return str((await tdb.roadmaps.insert_one({**plan, "knowledge_used": len(know), "created_at": now_iso()})).inserted_id)


@router.post("/roadmap/generate")
async def generate_roadmap(background: BackgroundTasks):
    return await _start("roadmap", _roadmap(), background)


REPORT = """You are the AI Business Manager for {biz}. Write the owner's {kind} business report in markdown, using ONLY the live data, alerts, goals and pending approvals below. Label actual vs estimate. No invented numbers. Be specific and brief.
Sections: 1) Headline (2 lines) 2) Key numbers (table: metric, this period, previous, note) 3) Alerts & risks 4) Progress to goals 5) {focus} 6) Decisions needed from the owner (approvals waiting, items needing input).
{extra}
DATA: {data}
ALERTS: {alerts}
GOALS: {goals}
PENDING APPROVALS: {approvals}"""
FOCUS = {"daily": "Top 3 actions for today", "weekly": "Plan for the coming week (5 actions with owner/measure)", "monthly": "Month review: what worked, what didn't, 3 strategic moves next month"}


async def build_report(kind: str) -> dict:
    snap = await snapshot()
    s = await tdb.settings.find_one({}, {"business.name": 1})
    goals = [{k: g[k] for k in ("title", "current", "target", "progress_pct")} for g in await goals_with_progress(snap)]
    pend = await tdb.approvals.count_documents({"status": "pending"})
    extra = "Weekly: compare this week vs last week for enquiries and paid jobs where data allows." if kind == "weekly" else ""
    text = await ai_complete(REPORT.format(biz=s["business"]["name"], kind=kind, focus=FOCUS[kind], extra=extra, data=json.dumps(snap, default=str)[:16000],
                                           alerts=json.dumps(insights(snap)), goals=json.dumps(goals), approvals=pend), f"Write the {kind} report.")
    doc = {"kind": kind, "title": f"{kind.title()} report - {snap['today']}", "body": text.strip(), "created_at": now_iso()}
    doc["id"] = str((await tdb.reports.insert_one(doc)).inserted_id)
    doc.pop("_id", None)
    return doc


@router.get("/reports")
async def list_reports(kind: str = ""):
    return outs(await tdb.reports.find({"kind": kind} if kind else {}, {"body": 0}).sort("created_at", -1).to_list(100))


@router.get("/reports/{rid}")
async def get_report(rid: str):
    r = out(await tdb.reports.find_one({"_id": oid(rid)}))
    if not r:
        raise HTTPException(404, "Report not found")
    return r


@router.post("/reports/generate")
async def generate_report(body: ReportIn, background: BackgroundTasks):
    async def run():
        return (await build_report(body.kind))["id"]
    return await _start(f"report_{body.kind}", run(), background)


DRAFT = """You write short, warm, professional UK-English emails for {biz}. For each item below write one email. Never invent prices, discounts or promises not in the item. No pressure tactics. Sign off as "{biz}".
Return ONLY a JSON array with one object per item, same order: {{"subject": "", "body": "plain text, 60-120 words"}}.
ITEMS: {items}"""


async def scan_candidates() -> list:
    t = now()
    cands = []
    pending = {a.get("ref_id") for a in await tdb.approvals.find({"status": {"$in": ["pending", "sent"]}}, {"ref_id": 1}).to_list(2000)}
    for q in await tdb.quotes.find({**LIVE, "status": "sent", "lead_id": {"$ne": None}, "created_at": {"$lte": (t - timedelta(days=2)).isoformat(), "$gte": (t - timedelta(days=30)).isoformat()}}).to_list(50):
        lead = await tdb.leads.find_one({"_id": oid(q["lead_id"])})
        if lead and lead.get("email") and str(q["_id"]) not in pending and not await is_suppressed(lead["email"]):
            cands.append({"kind": "quote_follow_up", "ref_id": str(q["_id"]), "lead_id": q["lead_id"], "to": lead["email"], "name": lead.get("name"),
                          "context": f"Quote for {q.get('service_name')} £{q.get('total')} sent {q['created_at'][:10]}, not yet booked."})
    for b in await tdb.bookings.find({**LIVE, "status": "completed", "review_submitted": {"$ne": True}, "date": {"$lte": (t - timedelta(days=4)).date().isoformat(), "$gte": (t - timedelta(days=30)).date().isoformat()}}).to_list(50):
        if str(b["_id"]) not in pending and not await tdb.reviews.find_one({"booking_id": str(b["_id"])}) and b["customer"].get("email") and not await is_suppressed(b["customer"]["email"]):
            cands.append({"kind": "review_request", "ref_id": str(b["_id"]), "lead_id": b.get("lead_id"), "to": b["customer"]["email"], "name": b["customer"]["name"],
                          "context": f"{b.get('service_name')} completed {b['date']}; no review yet. Ask kindly for honest feedback.", "link_token": b.get("feedback_token")})
    for p in await tdb.prospects.find({**LIVE, "status": {"$in": ["contacted", "interested"]}, "email": {"$nin": ["", None]}, "last_contacted_at": {"$lte": (t - timedelta(days=5)).isoformat()}}).to_list(30):
        if str(p["_id"]) not in pending and not await is_suppressed(p["email"]):
            cands.append({"kind": "prospect_follow_up", "ref_id": str(p["_id"]), "lead_id": None, "to": p["email"], "name": p.get("contact_name") or p.get("company"),
                          "context": f"Commercial prospect {p.get('company')} ({p.get('sector')}, {p.get('area')}), status {p['status']}, last contacted {str(p.get('last_contacted_at'))[:10]}. Offer a free site walkthrough."})
    return cands[:6]


@router.get("/approvals")
async def list_approvals(status: str = "pending"):
    return outs(await tdb.approvals.find({"status": status} if status else {}).sort("created_at", -1).to_list(200))


@router.post("/approvals/scan")
async def scan_approvals():
    cands = await scan_candidates()
    if not cands:
        return {"created": 0}
    s = await tdb.settings.find_one({}, {"business.name": 1})
    try:
        raw = await ai_complete(DRAFT.format(biz=s["business"]["name"], items=json.dumps([{k: c[k] for k in ("kind", "name", "context")} for c in cands])), "Write the emails.")
        drafts = json.loads(raw[raw.find("["): raw.rfind("]") + 1])
    except Exception:
        logger.exception("drafting failed")
        raise HTTPException(502, "Couldn't draft the follow-ups right now. Please try again.")
    for c, d in zip(cands, drafts):
        await tdb.approvals.insert_one({**c, "subject": str(d.get("subject", ""))[:200], "body": str(d.get("body", ""))[:5000], "status": "pending", "created_at": now_iso()})
    return {"created": min(len(cands), len(drafts))}


@router.patch("/approvals/{aid}")
async def edit_approval(aid: str, body: DraftEdit):
    if not (await tdb.approvals.update_one({"_id": oid(aid), "status": "pending"}, {"$set": body.model_dump(exclude_none=True)})).matched_count:
        raise HTTPException(404, "Draft not found or already handled")
    return {"ok": True}


@router.post("/approvals/{aid}/approve")
async def approve(aid: str, request: Request):
    a = await tdb.approvals.find_one({"_id": oid(aid), "status": "pending"})
    if not a:
        raise HTTPException(404, "Draft not found or already handled")
    link = None
    if a["kind"] == "review_request" and a.get("link_token"):
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        link = ("Leave your feedback", f"https://{host}/feedback/{a['ref_id']}?t={a['link_token']}")
    status = await log_comm(a["to"], "email", f"ai_{a['kind']}", a["subject"], a["body"], kind="follow_up", lead_id=a.get("lead_id"), link=link)
    await tdb.approvals.update_one({"_id": a["_id"]}, {"$set": {"status": "sent" if status == "sent" else "failed", "delivery_status": status, "approved_at": now_iso()}})
    if a.get("lead_id"):
        await add_event(a["lead_id"], "email", f"Owner-approved {a['kind'].replace('_', ' ')} emailed ({status})")
    if a["kind"] == "prospect_follow_up" and status == "sent":
        await tdb.prospects.update_one({"_id": oid(a["ref_id"])}, {"$set": {"last_contacted_at": now_iso()}})
    await audit("approval.send", f"{a['kind']} to {a['to']}: {status}")
    return {"status": status}


@router.post("/approvals/{aid}/reject")
async def reject(aid: str):
    if not (await tdb.approvals.update_one({"_id": oid(aid), "status": "pending"}, {"$set": {"status": "rejected", "rejected_at": now_iso()}})).matched_count:
        raise HTTPException(404, "Draft not found or already handled")
    return {"ok": True}


async def run_reports(kind: str):
    async for company in db.companies.find({"$or": [{"comped": True}, {"subscription_status": "active"}]}):
        set_tenant(company)
        try:
            if not await tdb.settings.find_one({}, {"_id": 1}):
                continue
            if kind == "research":
                from research import TOPICS, WEEKLY_CAP, connected, used_this_week
                from routes_knowledge import research_to_knowledge
                if not connected():
                    return
                week = now().isocalendar().week
                for i in range(4):
                    if await used_this_week() >= WEEKLY_CAP:
                        break
                    await research_to_knowledge(TOPICS[(week * 4 + i) % len(TOPICS)], "weekly_auto")
                continue
            await build_report(kind)
        except Exception:
            logger.exception("scheduled %s failed for %s", kind, company.get("slug"))


def _cron_auth(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or not secrets.compare_digest(auth[7:], os.environ["WEBHOOK_CRON_SECRET"]):
        raise HTTPException(401, "Unauthorized")


@cron.post("/manager-report/{kind}")
async def report_cron(kind: Literal["daily", "weekly", "research"], request: Request, background: BackgroundTasks):
    _cron_auth(request)
    run_id = request.headers.get("x-webhook-id") or secrets.token_hex(8)
    if (await db.cron_runs.update_one({"_id": run_id}, {"$setOnInsert": {"at": now_iso(), "name": f"report-{kind}"}}, upsert=True)).upserted_id is None:
        return {"ok": True, "duplicate": True}
    background.add_task(run_reports, kind)
    return {"ok": True}
