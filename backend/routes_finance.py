from datetime import date, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from business_data import COST_KEYS, DONE, job_cost, month_bounds, month_metrics
from core import audit, now, now_iso, oid, outs, require_owner, tdb

router = APIRouter(prefix="/api/admin/finance", dependencies=[Depends(require_owner)])
CATEGORIES = ("cleaner_wages", "subcontractors", "supplies", "equipment", "fuel_travel", "vehicle", "insurance", "software", "rent_office", "marketing_other", "tax_accounting", "other")


def _month(month: str) -> str:
    return month or now().astimezone(ZoneInfo("Europe/London")).strftime("%Y-%m")


class ExpenseIn(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    category: str
    amount: float = Field(gt=0, le=1_000_000)
    description: str = Field(default="", max_length=300)


class CostsIn(BaseModel):
    cleaner_pay: float = Field(default=0, ge=0)
    supplies: float = Field(default=0, ge=0)
    travel: float = Field(default=0, ge=0)
    notes: Optional[str] = Field(default="", max_length=300)


@router.get("/summary")
async def summary(month: str = ""):
    ym = _month(month)
    d = date.fromisoformat(f"{ym}-01")
    trend = []
    for _ in range(6):
        m = await month_metrics(d.strftime("%Y-%m"))
        trend.append({k: m[k] for k in ("month", "revenue", "profit", "jobs_booked_or_done", "jobs_missing_costs")})
        d = (d - timedelta(days=1)).replace(day=1)
    return {"metrics": await month_metrics(ym), "trend": trend[::-1], "categories": CATEGORIES}


@router.get("/expenses")
async def list_expenses(month: str = ""):
    start, end = month_bounds(_month(month))
    return outs(await tdb.expenses.find({"date": {"$gte": start, "$lt": end}}).sort("date", -1).to_list(2000))


@router.post("/expenses")
async def add_expense(body: ExpenseIn):
    if body.category not in CATEGORIES:
        raise HTTPException(400, "Unknown category")
    eid = str((await tdb.expenses.insert_one({**body.model_dump(), "created_at": now_iso()})).inserted_id)
    await audit("expense.add", f"{body.category} £{body.amount:.2f} {body.date}")
    return {"id": eid}


@router.delete("/expenses/{eid}")
async def delete_expense(eid: str):
    res = await tdb.expenses.delete_one({"_id": oid(eid)})
    if not res.deleted_count:
        raise HTTPException(404, "Expense not found")
    await audit("expense.delete", eid)
    return {"ok": True}


@router.get("/jobs")
async def jobs(month: str = ""):
    start, end = month_bounds(_month(month))
    docs = await tdb.bookings.find({"date": {"$gte": start, "$lt": end}, "status": {"$in": list(DONE)}, "payment_status": {"$in": ["paid", "deposit_paid"]}},
                                   {"timeline": 0, "input": 0, "lines": 0}).sort("date", 1).to_list(1000)
    return [{"id": str(b["_id"]), "date": b["date"], "service": b.get("service_name"), "customer": (b.get("customer") or {}).get("name"), "postcode": b.get("postcode"),
             "total": b.get("total"), "status": b["status"], "demo": b.get("demo", False), "job_costs": b.get("job_costs"), "cost_total": job_cost(b)} for b in docs]


@router.put("/jobs/{bid}/costs")
async def set_costs(bid: str, body: CostsIn):
    res = await tdb.bookings.update_one({"_id": oid(bid)}, {"$set": {"job_costs": {**body.model_dump(), "updated_at": now_iso()}}})
    if not res.matched_count:
        raise HTTPException(404, "Booking not found")
    await audit("job_costs.set", f"{bid}: " + ", ".join(f"{k} £{getattr(body, k):.2f}" for k in COST_KEYS))
    return {"ok": True}
