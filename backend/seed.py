import os
from datetime import timedelta

from core import db, hash_password, now, verify_password
from pricing import DEFAULT_SETTINGS, SERVICE_DEFAULTS, compute_quote
from routes_policies import policy_seed_docs

SOLID_BUSINESS = {"name": "Solid Clean Ltd", "website": "https://solidcleanltd.com", "phone": "020 3728 4419", "logo_url": "/brand/solidclean-logo.png",
                  "brand_primary": "#023F00", "brand_accent": "#8F7E22", "payment_mode": "full_upfront", "online_payments": True}
BUSINESS_DEFAULTS = {"phone": "[Business phone]", "logo_url": "", "brand_primary": "#0F766E", "brand_accent": "#0F172A", "payment_mode": "full_upfront",
                     "payment_instructions": "", "online_payments": True, "business_hours": "[Business hours]", "invoice_legal_name": "[Legal company name]",
                     "invoice_address": "[Registered address]", "company_number": "[Company number]", "vat_registered": False, "vat_number": ""}


async def migrate_company(company: dict):
    cid = str(company["_id"])
    s = await db.settings.find_one({"company_id": cid})
    if s:
        p = s["pricing"]
        p["services"] = [{**SERVICE_DEFAULTS, **x} for x in p["services"] if "airbnb" not in x["key"].lower() and "airbnb" not in x["name"].lower()]
        p.pop("parking_surcharge", None)
        p.setdefault("short_notice", {"days": 2, "type": "percent", "value": 0})
        p.setdefault("promo_codes", [])
        biz = {**BUSINESS_DEFAULTS, **s["business"], **(SOLID_BUSINESS if company["slug"] == "solid-clean" else {})}
        biz.pop("booking_page", None)
        await db.settings.update_one({"_id": s["_id"]}, {"$set": {"pricing": p, "business": biz}})
    for col in ("quotes", "bookings"):
        await db[col].update_many({"company_id": cid, "input.service": "airbnb"}, {"$set": {"input.service": "regular", "service": "regular", "service_name": "Residential / Regular Clean", "result.service_name": "Residential / Regular Clean"}})
        await db[col].update_many({"company_id": cid}, {"$unset": {"input.parking": ""}})
    await db.prospects.update_many({"company_id": cid, "sector": "airbnb_management"}, {"$set": {"sector": "property_management"}})
    await db.prospects.update_many({"company_id": cid, "company": "Kingston Stays Co (demo)"}, {"$set": {"company": "Kingston Lettings Co (demo)"}})
    if not await db.policies.find_one({"company_id": cid}):
        await db.policies.insert_many([{**d, "company_id": cid} for d in policy_seed_docs(company["name"])])

LEADS = [
    ("Hannah Clarke", "SW19 2AB", "google_ads", "booked", "end_of_tenancy", 2, 1, 3, 2),
    ("Tom Reeves", "CR0 4LP", "seo", "completed", "regular", 3, 2, 20, -10),
    ("Priya Shah", "KT1 3HD", "ai_chat", "quoted", "regular", 1, 1, 2, None),
    ("Daniel Okafor", "SM1 2QW", "google_ads", "completed", "end_of_tenancy", 3, 2, 25, -15),
    ("Lucy Fenwick", "TW9 1EJ", "website", "new", "carpet", 2, 1, 0, None),
    ("Marcus Bell", "SE22 8DN", "phone", "booked", "regular", 2, 1, 5, 4),
    ("Grace Holloway", "SW4 7AA", "seo", "quoted", "regular", 1, 1, 4, None),
    ("Oliver Grant", "CR2 6PS", "google_ads", "lost", "carpet", 3, 1, 12, None),
    ("Amelia Ward", "SW11 5RT", "referral", "completed", "regular", 2, 1, 40, -30),
]
PROSPECTS = [
    ("Southside Lettings (demo)", "letting_agent", "Sarah Lane", "SW19", "interested"),
    ("Croydon Property Partners (demo)", "property_management", "James Doyle", "CR0", "contacted"),
    ("Kingston Lettings Co (demo)", "letting_agent", "Mia Patel", "KT1", "to_contact"),
    ("Richmond Fitness Hub (demo)", "gym", "Ben Cole", "TW9", "meeting"),
    ("Sutton Build Group (demo)", "construction", "Ray Moss", "SM1", "not_interested"),
    ("Clapham Workspace (demo)", "office", "Anna Fry", "SW4", "to_contact"),
]
REVIEWS = [("Sophie M.", 5, "Brilliant end of tenancy clean, got our full deposit back.", 6),
           ("Raj P.", 5, "Punctual, friendly and very thorough.", 18),
           ("Chris T.", 4, "Good clean overall, missed a spot behind the oven.", 35),
           ("Leah W.", 2, "Cleaner arrived an hour late and I wasn't told in advance.", 50)]


def _iso(days: int) -> str:
    return (now() - timedelta(days=days)).isoformat()


async def seed_admin():
    email, password = os.environ["PLATFORM_ADMIN_EMAIL"].lower(), os.environ["PLATFORM_ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({"email": email, "password_hash": hash_password(password), "name": "Platform Admin", "role": "platform_admin", "active": True, "created_at": now().isoformat()})
    elif not verify_password(password, existing["password_hash"]):
        await db.users.update_one({"_id": existing["_id"]}, {"$set": {"password_hash": hash_password(password)}})


async def seed_demo_company() -> str:
    company = await db.companies.find_one({"slug": "solid-clean"})
    if not company:
        cid = str((await db.companies.insert_one({"name": "Solid Clean Ltd", "slug": "solid-clean", "plan_key": "pro", "subscription_status": "active",
                                                  "billing_interval": "month", "comped": True, "suspended": False, "country": "GB",
                                                  "owner_email": os.environ["ADMIN_EMAIL"].lower(), "created_at": now().isoformat()})).inserted_id)
    else:
        cid = str(company["_id"])
    email, password = os.environ["ADMIN_EMAIL"].lower(), os.environ["ADMIN_PASSWORD"]
    owner = await db.users.find_one({"email": email})
    if not owner:
        await db.users.insert_one({"email": email, "password_hash": hash_password(password), "name": "Solid Clean Owner", "role": "owner",
                                   "company_id": cid, "active": True, "job_role": "Owner", "created_at": now().isoformat()})
    else:
        await db.users.update_one({"_id": owner["_id"]}, {"$set": {"role": "owner", "company_id": cid, "active": True}})
        if not verify_password(password, owner["password_hash"]):
            await db.users.update_one({"_id": owner["_id"]}, {"$set": {"password_hash": hash_password(password)}})
    return cid


async def seed_demo(pricing: dict):
    today = now().date()
    for name, pc, src, status, svc, beds, baths, ago, offset in LEADS:
        email = name.lower().replace(" ", ".") + "@example.com"
        q = {"service": svc, "property_type": "flat", "bedrooms": beds, "bathrooms": baths, "living_rooms": 1,
             "condition": "good", "extras": [], "postcode": pc}
        res = compute_quote(pricing, q)
        lead = {"name": name, "email": email, "phone": "07700 900" + str(100 + ago), "postcode": pc, "source": src, "status": status,
                "type": "residential", "notes": "", "marketing_consent": False, "demo": True, "created_at": _iso(ago), "updated_at": _iso(ago),
                "follow_up_date": today.isoformat() if name == "Grace Holloway" else None,
                "timeline": [{"at": _iso(ago), "type": src, "text": f"Quote requested: {res['service_name']} £{res['total']:.2f}"}]}
        lid = str((await db.leads.insert_one(lead)).inserted_id)
        qstatus = "accepted" if offset is not None else ("declined" if status == "lost" else "sent")
        qid = str((await db.quotes.insert_one({"input": q, "result": res, "total": res["total"], "service_name": res["service_name"], "status": qstatus,
                                               "lead_id": lid, "source": src, "follow_ups_sent": 0, "demo": True, "created_at": _iso(ago)})).inserted_id)
        if offset is not None:
            await db.bookings.insert_one({"lead_id": lid, "quote_id": qid, "customer": {"name": name, "email": email, "phone": lead["phone"]},
                                          "postcode": pc, "service": svc, "service_name": res["service_name"], "input": q, "total": res["total"],
                                          "date": (today + timedelta(days=offset)).isoformat(), "slot": "11:00", "access_notes": "",
                                          "status": "completed" if offset < 0 else "confirmed", "payment_status": "paid", "source": src,
                                          "demo": True, "created_at": _iso(ago)})
    await db.conversations.insert_one({"channel": "web_chat", "status": "needs_human", "escalated": True, "demo": True, "lead_id": None,
                                       "escalation_reason": "Commercial office contract enquiry (approx. 4,000 sq ft, 3x weekly)",
                                       "summary": "Office manager asked about 3x weekly cleaning for a Croydon office. Commercial work needs a site survey, so it was escalated for a call-back.",
                                       "messages": [{"role": "assistant", "text": "Hello, you're through to Solid Clean Ltd. How can I help?", "at": _iso(1)},
                                                    {"role": "user", "text": "Hi, do you clean offices? We need 3 times a week in Croydon.", "at": _iso(1)},
                                                    {"role": "assistant", "text": "We do. Commercial cleaning is priced after a short site survey, so I'll ask a member of the team to call you. What's the best number?", "at": _iso(1)}],
                                       "created_at": _iso(1), "updated_at": _iso(1)})
    for company, sector, contact, area, status in PROSPECTS:
        await db.prospects.insert_one({"company": company, "sector": sector, "contact_name": contact, "email": contact.split()[0].lower() + "@example.com",
                                       "phone": "", "area": area, "website": "", "notes": "", "consent": False, "status": status, "steps_sent": 0 if status == "to_contact" else 1,
                                       "deal_value": 850.0 if status in ("interested", "meeting") else None, "email_check": "valid_format",
                                       "requires_consent": False, "history": [], "demo": True, "created_at": _iso(10)})
    for author, rating, text, ago in REVIEWS:
        await db.reviews.insert_one({"author": author, "rating": rating, "text": text, "platform": "google", "review_date": _iso(ago)[:10],
                                     "status": "needs_attention" if rating <= 3 else "responded", "response": "", "demo": True, "created_at": _iso(ago)})
    this_month, last_month = today.isoformat()[:7], (today.replace(day=1) - timedelta(days=1)).isoformat()[:7]
    for ch, m, amt in [("google_ads", this_month, 180), ("google_ads", last_month, 220), ("seo", this_month, 60),
                       ("seo", last_month, 60), ("cold_email", this_month, 40)]:
        await db.spend.insert_one({"channel": ch, "month": m, "amount": float(amt), "notes": "Demo figure", "demo": True, "created_at": now().isoformat()})


async def seed_all():
    await db.users.create_index("email", unique=True)
    await db.companies.create_index("slug", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.leads.create_index([("company_id", 1), ("email", 1)])
    await db.bookings.create_index([("company_id", 1), ("date", 1), ("slot", 1)])
    if "email_1" in await db.suppressions.index_information():
        await db.suppressions.drop_index("email_1")
    await db.suppressions.create_index([("company_id", 1), ("email", 1)], unique=True)
    await db.payment_transactions.create_index("session_id")
    await db.saas_invoices.create_index("invoice_id", unique=True)
    await seed_admin()
    cid = await seed_demo_company()
    if not await db.settings.find_one({"key": "main"}):
        await db.settings.insert_one({**DEFAULT_SETTINGS, "company_id": cid})
    settings = await db.settings.find_one({"key": "main", "$or": [{"company_id": cid}, {"company_id": {"$exists": False}}]})
    if not settings.get("demo_seeded"):
        await seed_demo(settings["pricing"])
        await db.settings.update_one({"_id": settings["_id"]}, {"$set": {"demo_seeded": True}})
    for col in ("settings", "leads", "quotes", "bookings", "conversations", "prospects", "reviews", "spend", "communications", "suppressions", "payment_transactions"):
        await db[col].update_many({"company_id": {"$exists": False}}, {"$set": {"company_id": cid}})
    async for company in db.companies.find({}):
        await migrate_company(company)
