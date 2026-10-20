from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import audit, current_actor, now_iso, outs, require_admin, require_owner, tdb

router = APIRouter(prefix="/api/admin/policies", dependencies=[Depends(require_admin)])
R = "[REVIEW REQUIRED: {}]"

POLICY_DEFS = [
    ("booking", "Booking policy", "public", True, "Bookings are made online by selecting a service, an available appointment and paying the required amount. A booking is confirmed only once payment succeeds and a confirmation with a booking reference is sent. Where a price cannot be calculated automatically, we provide a quotation; a quotation becomes a booking once accepted and paid. " + R.format("confirm quotation validity period and any other booking conditions")),
    ("payment", "Payment policy", "public", True, "Full payment is required upfront at the time of booking to secure your appointment. Card payments are processed securely by Stripe; we never store full card details. " + R.format("confirm accepted payment methods and invoicing terms")),
    ("cancellation", "Cancellation & rescheduling", "public", True, "Please contact us at least 24 hours in advance to reschedule or cancel. " + R.format("set cancellation charges, refund rules and late-cancellation terms - none are applied until approved")),
    ("eot_guarantee", "3-day End of Tenancy cleaning guarantee", "public", False, "If you are not satisfied with an End of Tenancy clean, please report the issue within 3 days of the clean with your booking reference, a description and photographs. We will review the report and, where appropriate, arrange a remedy. " + R.format("define eligible issues, evidence required and remedies")),
    ("scope", "Scope of services", "public", False, "What is included and excluded is listed for each service. " + R.format("confirm inclusions/exclusions per service in Services settings")),
    ("property_condition", "Property condition", "public", False, "Prices assume the property condition described when booking. If a property is significantly dirtier than described, we will explain the situation and provide a revised quotation. No additional charge is applied unless you agree to it before the work continues."),
    ("access", "Access & missed appointments", "public", False, "Please ensure our team can access the property at the booked time. " + R.format("define what happens if access cannot be obtained, including waiting time and any charges")),
    ("complaints", "Complaints", "public", False, "If something is not right, contact us with your booking reference, a description and any photographs. We will acknowledge your complaint, review it and let you know the outcome. " + R.format("confirm response timescales")),
    ("damage", "Damage & liability", "public", False, "Please report any alleged damage as soon as possible with your booking reference, a description and photographs. We will investigate every report fairly. This policy does not affect your statutory rights. " + R.format("confirm insurance details and claims process")),
    ("preparation", "Customer preparation", "public", False, "Please ensure the property is accessible and has working electricity and water. Service-specific preparation is shown with each service. " + R.format("confirm preparation requirements")),
    ("privacy", "Privacy policy", "public", False, "Solid Clean Ltd collects your name, contact details, property address and booking details to provide quotations, bookings and customer service. Payments are processed by Stripe. We use an AI provider to help answer enquiries. We only send marketing with your consent and you can unsubscribe at any time. You can request access to, correction of or deletion of your personal data by contacting us. " + R.format("confirm retention periods, ICO registration number and data controller contact details")),
    ("terms", "Terms & conditions", "public", True, "These terms cover use of this website, quotations, bookings, payments, cancellations and complaints. Nothing in these terms affects your statutory rights as a consumer. " + R.format("full terms require your legal review")),
    ("cookies", "Cookie notice", "public", False, "This booking site uses only essential browser storage needed for it to work (for example remembering your booking session). No advertising or analytics cookies are set. " + R.format("update if analytics or advertising tags are added - consent will then be required")),
    ("staff_conduct", "Staff handbook: conduct, confidentiality & safety", "staff", False, R.format("professional conduct, confidentiality, attendance, quality standards, incident reporting and health & safety rules")),
]


def policy_seed_docs(company_name: str):
    return [{"key": k, "title": t, "audience": a, "require_acceptance": req, "order": i,
             "draft_content": c.replace("Solid Clean Ltd", company_name), "needs_review": True, "effective_date": "",
             "published_version": 0, "published_content": "", "published_at": None, "versions": [], "updated_at": now_iso()}
            for i, (k, t, a, req, c) in enumerate(POLICY_DEFS)]


class PolicyIn(BaseModel):
    title: str
    draft_content: str
    needs_review: bool = True
    effective_date: str = ""
    require_acceptance: bool = False


class PublishIn(BaseModel):
    confirm: bool


@router.get("")
async def list_policies(ctx=Depends(require_admin)):
    query = {} if ctx["user"]["role"] == "owner" else {"audience": "staff"}
    return outs(await tdb.policies.find(query).sort("order", 1).to_list(100))


async def _get(key: str):
    p = await tdb.policies.find_one({"key": key})
    if not p:
        raise HTTPException(404, "Policy not found")
    return p


@router.put("/{key}", dependencies=[Depends(require_owner)])
async def save_draft(key: str, body: PolicyIn):
    await _get(key)
    await tdb.policies.update_one({"key": key}, {"$set": {**body.model_dump(), "updated_at": now_iso()}})
    await audit("policy.draft", key)
    return {"ok": True}


@router.post("/{key}/publish", dependencies=[Depends(require_owner)])
async def publish(key: str, body: PublishIn):
    p = await _get(key)
    if not body.confirm:
        raise HTTPException(400, "Confirmation required")
    if "[REVIEW REQUIRED" in p["draft_content"]:
        raise HTTPException(400, "Replace every [REVIEW REQUIRED: ...] marker with your approved wording before publishing")
    v = p["published_version"] + 1
    version = {"version": v, "content": p["draft_content"], "title": p["title"], "effective_date": p.get("effective_date") or now_iso()[:10],
               "published_at": now_iso(), "published_by": current_actor.get()}
    await tdb.policies.update_one({"key": key}, {"$set": {"published_version": v, "published_content": p["draft_content"], "needs_review": False, "unpublished": False,
                                                          "published_at": version["published_at"], "effective_date": version["effective_date"]},
                                                 "$push": {"versions": version}})
    await audit("policy.publish", f"{key} v{v}")
    return {"version": v}


@router.post("/{key}/unpublish", dependencies=[Depends(require_owner)])
async def unpublish(key: str, body: PublishIn):
    p = await _get(key)
    if not body.confirm:
        raise HTTPException(400, "Confirmation required")
    await tdb.policies.update_one({"_id": p["_id"]}, {"$set": {"unpublished": True, "require_acceptance": False, "unpublished_at": now_iso()}})
    await audit("policy.unpublish", f"{key} v{p['published_version']}")
    return {"ok": True}
