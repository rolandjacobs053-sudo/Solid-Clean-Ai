import asyncio
import copy
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from core import (access_state, current_user, db, hash_password, now, now_iso, oid, out, outs,
                  plan_features, require_admin, require_member_any, require_owner, require_platform)
from pricing import DEFAULT_SETTINGS
from routes_auth import set_auth_cookies

router = APIRouter(prefix="/api")
platform = APIRouter(prefix="/api/platform", dependencies=[Depends(require_platform)])
logger = logging.getLogger(__name__)
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
PLATFORM_NAME = os.environ["PLATFORM_NAME"]
CURRENCY = "gbp"
TRIAL_DAYS = 14
EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
DEFAULT_PLANS = [
    {"key": "starter", "name": "Starter", "monthly_price": 49.0, "annual_price": 490.0, "max_staff": 3, "order": 1, "active": True,
     "description": "Instant quotes, online booking, CRM and analytics for small teams.", "features": ["quotes_bookings", "crm", "analytics"]},
    {"key": "growth", "name": "Growth", "monthly_price": 99.0, "annual_price": 990.0, "max_staff": 10, "order": 2, "active": True,
     "description": "Adds the AI receptionist and review management.", "features": ["quotes_bookings", "crm", "analytics", "ai_receptionist", "reviews"]},
    {"key": "pro", "name": "Pro", "monthly_price": 199.0, "annual_price": 1990.0, "max_staff": 50, "order": 3, "active": True,
     "description": "Everything, plus commercial cold-email outreach and marketing analytics.", "features": ["quotes_bookings", "crm", "analytics", "ai_receptionist", "reviews", "outreach", "marketing"]},
]


def _d(obj) -> dict:
    return json.loads(str(obj))


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None


def _lookup(plan_key: str, interval: str) -> str:
    return f"{plan_key}_{'monthly' if interval == 'month' else 'annual'}"


def sync_plan_to_stripe(plan: dict):
    product = next((p for p in stripe.Product.list(active=True, limit=100).auto_paging_iter()
                    if _d(p).get("metadata", {}).get("emergent_product_id") == f"plan_{plan['key']}"), None)
    if not product:
        product = stripe.Product.create(name=f"{PLATFORM_NAME} {plan['name']}", tax_code="txcd_10103001",
                                        metadata={"managed_by": "emergent", "emergent_product_id": f"plan_{plan['key']}"})
    for interval, field in (("month", "monthly_price"), ("year", "annual_price")):
        lk, amount = _lookup(plan["key"], interval), int(round(plan[field] * 100))
        existing = stripe.Price.list(lookup_keys=[lk], active=True, limit=1).data
        if existing and existing[0].unit_amount == amount:
            continue
        if existing:
            stripe.Price.modify(existing[0].id, active=False)
        stripe.Price.create(product=product.id, unit_amount=amount, currency=CURRENCY, recurring={"interval": interval},
                            lookup_key=lk, transfer_lookup_key=True)


async def seed_plans():
    for plan in DEFAULT_PLANS:
        if not await db.plans.find_one({"key": plan["key"]}):
            await db.plans.insert_one(dict(plan, created_at=now_iso()))
    for plan in await db.plans.find({}).to_list(50):
        try:
            await asyncio.to_thread(sync_plan_to_stripe, plan)
        except stripe.error.StripeError:
            logger.exception("stripe plan sync failed for %s", plan["key"])


def _session(kwargs):
    for extra in ({"managed_payments": {"enabled": True}}, {"automatic_tax": {"enabled": True}, "billing_address_collection": "required"}, {}):
        try:
            return stripe.checkout.Session.create(**kwargs, **extra)
        except stripe.error.InvalidRequestError:
            if not extra:
                raise
            logger.info("checkout fallback from %s", list(extra))


async def apply_subscription(company_id: str, sub: dict):
    item = sub["items"]["data"][0]
    plan_key, _, iv = (item["price"].get("lookup_key") or "").rpartition("_")
    company = await db.companies.find_one({"_id": oid(company_id)})
    upd = {"stripe_subscription_id": sub["id"], "stripe_customer_id": sub["customer"], "subscription_status": sub["status"],
           "billing_interval": "year" if iv == "annual" else "month", "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
           "current_period_end": _iso(sub.get("current_period_end") or item.get("current_period_end"))}
    if plan_key:
        upd["plan_key"] = plan_key
    upd["past_due_since"] = (company.get("past_due_since") or now_iso()) if sub["status"] == "past_due" else None
    await db.companies.update_one({"_id": company["_id"]}, {"$set": upd})


async def record_invoice(inv: dict, company_id: str):
    await db.saas_invoices.update_one({"invoice_id": inv["id"]}, {"$set": {
        "invoice_id": inv["id"], "company_id": company_id, "status": inv["status"], "currency": inv["currency"],
        "amount_due": inv["amount_due"] / 100, "amount_paid": inv["amount_paid"] / 100, "url": inv.get("hosted_invoice_url"),
        "created_at": _iso(inv["created"])}}, upsert=True)


async def _company_for(obj: dict):
    cid = (obj.get("metadata") or {}).get("company_id")
    if cid:
        return await db.companies.find_one({"_id": oid(cid)})
    return await db.companies.find_one({"stripe_customer_id": obj.get("customer")})


async def handle_billing_event(kind: str, obj: dict) -> bool:
    if kind == "checkout.session.completed" and obj.get("mode") == "subscription":
        sub = _d(await asyncio.to_thread(stripe.Subscription.retrieve, obj["subscription"]))
        await apply_subscription(obj["metadata"]["company_id"], sub)
    elif kind.startswith("customer.subscription."):
        company = await _company_for(obj)
        if company:
            await apply_subscription(str(company["_id"]), obj)
    elif kind in ("invoice.paid", "invoice.payment_failed"):
        company = await _company_for(obj)
        if not company:
            return True
        await record_invoice(obj, str(company["_id"]))
        if kind == "invoice.payment_failed":
            await db.companies.update_one({"_id": company["_id"], "past_due_since": None}, {"$set": {"past_due_since": now_iso()}})
            await db.companies.update_one({"_id": company["_id"]}, {"$set": {"subscription_status": "past_due"}})
            await db.communications.insert_one({"company_id": str(company["_id"]), "to": company.get("owner_email"), "channel": "email",
                                                "template": "billing_payment_failed", "kind": "transactional", "status": "simulated",
                                                "subject": f"{PLATFORM_NAME}: payment failed", "created_at": now_iso(),
                                                "body": "We couldn't take your subscription payment. Please update your card in Billing within 7 days to keep access."})
    else:
        return False
    return True


# ---------- signup & staff ----------
class SignupIn(BaseModel):
    company_name: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(pattern=EMAIL_RE)
    password: str = Field(min_length=8, max_length=128)
    country: str = ""


async def _unique_slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "company"
    slug, i = base, 1
    while await db.companies.find_one({"slug": slug}):
        i += 1
        slug = f"{base}-{i}"
    return slug


@router.post("/auth/signup")
async def signup(body: SignupIn, response: Response):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "An account with this email already exists")
    company = {"name": body.company_name.strip(), "slug": await _unique_slug(body.company_name), "country": body.country,
               "plan_key": "growth", "subscription_status": "trialing", "billing_interval": "month", "owner_email": email,
               "trial_ends_at": (now() + timedelta(days=TRIAL_DAYS)).isoformat(), "suspended": False, "comped": False, "created_at": now_iso()}
    cid = str((await db.companies.insert_one(company)).inserted_id)
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    settings["business"]["name"] = company["name"]
    await db.settings.insert_one({**settings, "company_id": cid})
    user = {"email": email, "password_hash": hash_password(body.password), "name": body.name, "role": "owner",
            "company_id": cid, "active": True, "job_role": "Owner", "created_at": now_iso()}
    uid = str((await db.users.insert_one(user)).inserted_id)
    set_auth_cookies(response, uid, email)
    user.pop("password_hash")
    return out({**user, "_id": uid})


class StaffIn(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(pattern=EMAIL_RE)
    password: str = Field(min_length=8)
    job_role: str = "Cleaner"
    phone: str = ""


class StaffPatch(BaseModel):
    active: Optional[bool] = None
    job_role: Optional[str] = None
    phone: Optional[str] = None


@router.get("/admin/staff")
async def list_staff(ctx=Depends(require_admin)):
    return outs(await db.users.find({"company_id": str(ctx["company"]["_id"])}, {"password_hash": 0}).sort("created_at", 1).to_list(500))


@router.post("/admin/staff")
async def add_staff(body: StaffIn, ctx=Depends(require_owner)):
    company = ctx["company"]
    if not access_state(company)["ok"]:
        raise HTTPException(402, "Subscription inactive")
    plan = await db.plans.find_one({"key": company.get("plan_key")}) or {}
    active = await db.users.count_documents({"company_id": str(company["_id"]), "active": {"$ne": False}})
    if not company.get("comped") and active >= plan.get("max_staff", 1):
        raise HTTPException(403, f"Your plan allows {plan.get('max_staff')} active users - upgrade to add more")
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "A user with this email already exists")
    doc = {**body.model_dump(exclude={"password"}), "email": email, "password_hash": hash_password(body.password), "role": "staff",
           "company_id": str(company["_id"]), "active": True, "created_at": now_iso()}
    return {"id": str((await db.users.insert_one(doc)).inserted_id)}


@router.patch("/admin/staff/{uid}")
async def patch_staff(uid: str, body: StaffPatch, ctx=Depends(require_owner)):
    user = await db.users.find_one({"_id": oid(uid), "company_id": str(ctx["company"]["_id"])})
    if not user:
        raise HTTPException(404, "User not found")
    if user["role"] == "owner" and body.active is False:
        raise HTTPException(400, "The owner account can't be deactivated")
    await db.users.update_one({"_id": user["_id"]}, {"$set": body.model_dump(exclude_none=True)})
    return {"ok": True}


# ---------- billing ----------
class CheckoutIn(BaseModel):
    plan_key: str
    interval: str = Field(pattern="^(month|year)$")
    origin_url: str


async def _summary(company_id: str):
    company = await db.companies.find_one({"_id": oid(company_id)})
    plans = await db.plans.find({"active": True}).sort("order", 1).to_list(20)
    invoices = await db.saas_invoices.find({"company_id": company_id}).sort("created_at", -1).to_list(24)
    fields = ("name", "slug", "plan_key", "subscription_status", "billing_interval", "trial_ends_at", "current_period_end",
              "cancel_at_period_end", "past_due_since", "comped", "suspended", "stripe_subscription_id")
    return {"company": {k: company.get(k) for k in fields}, "access": access_state(company), "plans": outs(plans), "invoices": outs(invoices)}


@router.get("/billing/summary")
async def billing_summary(ctx=Depends(require_member_any)):
    return await _summary(str(ctx["company"]["_id"]))


@router.get("/billing/sync")
async def billing_sync(session_id: str = "", ctx=Depends(require_member_any)):
    company, cid = ctx["company"], str(ctx["company"]["_id"])
    sub_id = company.get("stripe_subscription_id")
    if session_id:
        sess = _d(await asyncio.to_thread(stripe.checkout.Session.retrieve, session_id))
        if sess.get("metadata", {}).get("company_id") != cid:
            raise HTTPException(404, "Session not found")
        sub_id = sess.get("subscription") or sub_id
        await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"status": sess["status"], "payment_status": sess["payment_status"], "updated_at": now_iso()}})
    if sub_id:
        await apply_subscription(cid, _d(await asyncio.to_thread(stripe.Subscription.retrieve, sub_id)))
        company = await db.companies.find_one({"_id": company["_id"]})
        for inv in (await asyncio.to_thread(stripe.Invoice.list, customer=company["stripe_customer_id"], limit=12)).data:
            await record_invoice(_d(inv), cid)
    return await _summary(cid)


@router.post("/billing/checkout")
async def billing_checkout(body: CheckoutIn, ctx=Depends(require_owner)):
    company, user = ctx["company"], ctx["user"]
    cid = str(company["_id"])
    if not await db.plans.find_one({"key": body.plan_key, "active": True}):
        raise HTTPException(404, "Plan not found")
    prices = (await asyncio.to_thread(stripe.Price.list, lookup_keys=[_lookup(body.plan_key, body.interval)], active=True, limit=1)).data
    if not prices:
        raise HTTPException(500, "Plan price not configured in Stripe")
    price = prices[0]
    if company.get("stripe_subscription_id") and company.get("subscription_status") in ("active", "past_due", "trialing"):
        sub = _d(await asyncio.to_thread(stripe.Subscription.retrieve, company["stripe_subscription_id"]))
        new = await asyncio.to_thread(stripe.Subscription.modify, sub["id"], items=[{"id": sub["items"]["data"][0]["id"], "price": price.id}],
                                      proration_behavior="create_prorations", cancel_at_period_end=False)
        await apply_subscription(cid, _d(new))
        return {"changed": True}
    customer = company.get("stripe_customer_id")
    if not customer:
        customer = (await asyncio.to_thread(stripe.Customer.create, email=user["email"], name=company["name"], metadata={"company_id": cid})).id
        await db.companies.update_one({"_id": company["_id"]}, {"$set": {"stripe_customer_id": customer}})
    origin = body.origin_url.rstrip("/")
    kwargs = dict(mode="subscription", customer=customer, line_items=[{"price": price.id, "quantity": 1}],
                  success_url=f"{origin}/admin/billing?session_id={{CHECKOUT_SESSION_ID}}", cancel_url=f"{origin}/admin/billing",
                  metadata={"company_id": cid, "kind": "subscription"}, subscription_data={"metadata": {"company_id": cid}})
    session = await asyncio.to_thread(_session, kwargs)
    await db.payment_transactions.insert_one({"session_id": session.id, "company_id": cid, "kind": "subscription", "lookup_key": price.lookup_key,
                                              "amount": price.unit_amount / 100, "currency": price.currency, "status": "initiated",
                                              "payment_status": "pending", "created_at": now_iso(), "updated_at": now_iso()})
    return {"checkout_url": session.url}


async def _set_cancel(ctx, value: bool):
    company = ctx["company"]
    if not company.get("stripe_subscription_id"):
        raise HTTPException(400, "No paid subscription to change")
    sub = await asyncio.to_thread(stripe.Subscription.modify, company["stripe_subscription_id"], cancel_at_period_end=value)
    await apply_subscription(str(company["_id"]), _d(sub))
    return await _summary(str(company["_id"]))


@router.post("/billing/cancel")
async def billing_cancel(ctx=Depends(require_owner)):
    return await _set_cancel(ctx, True)


@router.post("/billing/resume")
async def billing_resume(ctx=Depends(require_owner)):
    return await _set_cancel(ctx, False)


class PortalIn(BaseModel):
    origin_url: str


def _portal(customer: str, return_url: str):
    try:
        return stripe.billing_portal.Session.create(customer=customer, return_url=return_url)
    except stripe.error.InvalidRequestError:
        conf = stripe.billing_portal.Configuration.create(features={"payment_method_update": {"enabled": True}, "invoice_history": {"enabled": True}})
        return stripe.billing_portal.Session.create(customer=customer, return_url=return_url, configuration=conf.id)


@router.post("/billing/portal")
async def billing_portal(body: PortalIn, ctx=Depends(require_owner)):
    customer = ctx["company"].get("stripe_customer_id")
    if not customer:
        raise HTTPException(400, "Subscribe to a plan first")
    sess = await asyncio.to_thread(_portal, customer, f"{body.origin_url.rstrip('/')}/admin/billing")
    return {"url": sess.url}


@router.get("/saas/plans")
async def public_plans():
    return outs(await db.plans.find({"active": True}).sort("order", 1).to_list(20))


# ---------- platform admin ----------
class CompanyPatch(BaseModel):
    suspended: Optional[bool] = None
    extend_trial_days: Optional[int] = Field(None, ge=1, le=90)
    comped: Optional[bool] = None


class PlanIn(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9]{2,20}$")
    name: str
    description: str = ""
    monthly_price: float = Field(ge=1)
    annual_price: float = Field(ge=1)
    max_staff: int = Field(ge=1)
    features: List[str]
    active: bool = True
    order: int = 9


def _mrr(company: dict, plans: dict) -> float:
    plan = plans.get(company.get("plan_key"))
    if not plan or company.get("comped") or company.get("subscription_status") not in ("active", "past_due"):
        return 0.0
    return plan["annual_price"] / 12 if company.get("billing_interval") == "year" else plan["monthly_price"]


@platform.get("/overview")
async def platform_overview():
    companies = await db.companies.find({}).to_list(10000)
    plans = {p["key"]: p for p in await db.plans.find({}).to_list(50)}
    counts = {}
    for c in companies:
        counts[c.get("subscription_status", "none")] = counts.get(c.get("subscription_status", "none"), 0) + 1
    mrr = round(sum(_mrr(c, plans) for c in companies), 2)
    paid = await db.saas_invoices.find({"status": "paid"}).to_list(10000)
    return {"companies": len(companies), "by_status": counts, "mrr": mrr, "arr": round(mrr * 12, 2),
            "signups_30d": len([c for c in companies if c["created_at"] > (now() - timedelta(days=30)).isoformat()]),
            "collected": round(sum(i["amount_paid"] for i in paid), 2),
            "failed_payments": await db.saas_invoices.count_documents({"status": {"$in": ["open", "uncollectible"]}}),
            "by_plan": [{"plan": k, "companies": len([c for c in companies if c.get("plan_key") == k])} for k in plans]}


@platform.get("/companies")
async def platform_companies():
    plans = {p["key"]: p for p in await db.plans.find({}).to_list(50)}
    rows = []
    for c in await db.companies.find({}).sort("created_at", -1).to_list(5000):
        cid = str(c["_id"])
        c.update(access=access_state(c), mrr=_mrr(c, plans), users=await db.users.count_documents({"company_id": cid}),
                 leads=await db.leads.count_documents({"company_id": cid}), bookings=await db.bookings.count_documents({"company_id": cid}))
        rows.append(c)
    return outs(rows)


@platform.patch("/companies/{cid}")
async def platform_patch_company(cid: str, body: CompanyPatch):
    company = await db.companies.find_one({"_id": oid(cid)})
    if not company:
        raise HTTPException(404, "Company not found")
    upd = body.model_dump(exclude_none=True, exclude={"extend_trial_days"})
    if body.extend_trial_days:
        start = max(company.get("trial_ends_at") or now_iso(), now_iso())
        upd["trial_ends_at"] = (datetime.fromisoformat(start) + timedelta(days=body.extend_trial_days)).isoformat()
        if company.get("subscription_status") in ("trialing", None):
            upd["subscription_status"] = "trialing"
    await db.companies.update_one({"_id": company["_id"]}, {"$set": upd})
    return {"ok": True}


@platform.get("/plans")
async def platform_plans():
    return outs(await db.plans.find({}).sort("order", 1).to_list(50))


@platform.put("/plans")
async def platform_save_plan(body: PlanIn):
    plan = body.model_dump()
    await db.plans.update_one({"key": body.key}, {"$set": plan, "$setOnInsert": {"created_at": now_iso()}}, upsert=True)
    try:
        await asyncio.to_thread(sync_plan_to_stripe, plan)
    except stripe.error.StripeError as e:
        raise HTTPException(502, f"Saved, but Stripe sync failed: {e.user_message or e}")
    return {"ok": True}


@platform.get("/payments")
async def platform_payments():
    names = {str(c["_id"]): c["name"] async for c in db.companies.find({}, {"name": 1})}
    rows = await db.saas_invoices.find({}).sort("created_at", -1).to_list(500)
    for r in rows:
        r["company_name"] = names.get(r["company_id"], "—")
    return outs(rows)


@router.get("/auth/me")
async def me(request: Request):
    user = await current_user(request)
    data = out(user)
    if user.get("company_id"):
        company = await db.companies.find_one({"_id": oid(user["company_id"])})
        data["company"] = {"id": user["company_id"], "name": company["name"], "slug": company["slug"], "plan_key": company.get("plan_key"),
                           "subscription_status": company.get("subscription_status"), "trial_ends_at": company.get("trial_ends_at"),
                           "comped": company.get("comped", False), "access": access_state(company),
                           "features": await plan_features(company)}
    return data
