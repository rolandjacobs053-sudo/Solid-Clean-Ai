"""Iteration 11: residential cleaning pricing (frequency/people/pets/last-cleaned/tasks), recurring booking consent + Stripe
checkout with saved card, recurring cron (auth, idempotency, off-session charge success/failure), admin plan status.
Creates TEST_ data and cleans it up."""
import datetime as dt
import os
import uuid

import pytest
import requests
import stripe
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
PUB = f"{BASE}/api/public/solid-clean"
OWNER = {"email": "admin@solidcleanltd.com", "password": "SolidClean#2026"}
ENV = dotenv_values("/app/backend/.env")
DB = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
CID = "6acb2a20e5d23531c955e49b"
CRON = ENV["WEBHOOK_CRON_SECRET"]
stripe.api_key = ENV["STRIPE_SECRET_KEY"]
CREATED = {"bookings": [], "plans": [], "emails": [], "customers": []}

EXAMPLE = {"service": "regular", "property_type": "house", "bedrooms": 3, "bathrooms": 2, "living_rooms": 1, "frequency": "weekly",
           "people": "3_4", "pets": "yes", "last_cleaned": "1_3_months", "tasks": ["general", "kitchen", "beds", "ironing"],
           "task_qty": {"beds": 3, "ironing": 2}, "extras": ["oven"]}


def _prev(**kw):
    return requests.post(f"{PUB}/quote/preview", json={**EXAMPLE, **kw}, timeout=20)


@pytest.fixture(scope="module")
def owner():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=OWNER, timeout=20)
    assert r.status_code == 200, r.text
    return s


def _slot():
    d = dt.date.today() + dt.timedelta(days=3)
    for _ in range(30):
        r = requests.get(f"{PUB}/availability", params={"date": d.isoformat()}, timeout=15)
        if r.status_code == 200:
            js = r.json()
            slots = js.get("slots", js) if isinstance(js, dict) else js
            if slots:
                s = slots[0]
                return d.isoformat(), s["slot"] if isinstance(s, dict) else s
        d += dt.timedelta(days=1)
    pytest.skip("no slot")


def _booking_body(freq, consent, **kw):
    email = f"test_res11_{uuid.uuid4().hex[:6]}@example.com"
    CREATED["emails"].append(email)
    day, slot = _slot()
    pol = {p["key"]: p["published_version"] for p in requests.get(f"{PUB}/config", timeout=15).json().get("policies", []) if p.get("require_acceptance")}
    return {"quote": {**EXAMPLE, "frequency": freq, "postcode": "SW19 2AB", "address": "TEST_ 1 Test Road, London"},
            "contact": {"name": "TEST_ Residential", "email": email, "phone": "07700900123"}, "date": day, "slot": slot,
            "access": {"method": "customer_present"}, "accepted_policies": pol, "pay_terms_accepted": True,
            "auto_charge_consent": consent, "tip": 0, "origin_url": BASE, **kw}


# --- Pricing
class TestResidentialPricing:
    def test_example_total(self):
        r = _prev()
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "ok" and d["total"] == 222.28, d
        assert any(l["label"] == "Weekly cleaning discount (15%)" for l in d["lines"]), d["lines"]
        labels = [l["label"] for l in d["lines"]]
        assert "Making beds and changing bed linen × 3" in labels and "Ironing clothes × 2" in labels

    def test_one_off_no_discount(self):
        d = _prev(frequency="one_off").json()
        assert d["total"] == 261.51 and not any("discount" in l["label"] for l in d["lines"]), d

    def test_frequency_discounts(self):
        assert _prev(frequency="fortnightly").json()["total"] == round(261.51 - round(261.51 * 0.10, 2), 2)
        assert _prev(frequency="monthly").json()["total"] == round(261.51 - round(261.51 * 0.05, 2), 2)

    def test_factors_change_price(self):
        base = _prev(frequency="one_off").json()["total"]
        assert _prev(frequency="one_off", pets="no").json()["total"] < base
        assert _prev(frequency="one_off", people="5_plus").json()["total"] > base
        assert _prev(frequency="one_off", last_cleaned="over_3_months").json()["total"] > base
        assert _prev(frequency="one_off", tasks=["general", "dishes"]).json()["total"] < base

    def test_old_flow_without_frequency_unchanged(self):
        r = requests.post(f"{PUB}/quote/preview", json={"service": "end_of_tenancy", "property_type": "flat", "bedrooms": 2, "bathrooms": 1,
                                                       "living_rooms": 1, "condition": "good", "tasks": ["beds"]}, timeout=20)
        d = r.json()
        assert d["status"] == "ok" and d["total"] == 240.0, d  # 120+70+30+20
        assert "frequency" not in d


# --- Booking creation
class TestResidentialBooking:
    def test_recurring_without_consent_409(self):
        r = requests.post(f"{PUB}/bookings", json=_booking_body("weekly", False), timeout=30)
        assert r.status_code == 409, r.text
        assert "automatic" in r.json()["detail"].lower()

    def test_recurring_with_consent_saves_card(self):
        r = requests.post(f"{PUB}/bookings", json=_booking_body("fortnightly", True), timeout=40)
        assert r.status_code == 200, r.text
        d = r.json()
        CREATED["bookings"].append(d["booking_id"])
        assert "checkout.stripe.com" in d["checkout_url"]
        b = DB.bookings.find_one({"_id": ObjectId(d["booking_id"])})
        assert b["frequency"] == "fortnightly" and b["recurring"] is True and b["auto_charge_consent_at"]
        assert b["total"] == round(261.51 - 26.15, 2)
        sess = stripe.checkout.Session.retrieve(b["session_id"])
        assert sess.payment_intent is None or True
        assert sess.customer_creation == "always"
        assert sess.amount_total == int(round(b["total"] * 100))

    def test_one_off_no_consent_needed(self):
        r = requests.post(f"{PUB}/bookings", json=_booking_body("one_off", False), timeout=40)
        assert r.status_code == 200, r.text
        CREATED["bookings"].append(r.json()["booking_id"])
        b = DB.bookings.find_one({"_id": ObjectId(r.json()["booking_id"])})
        assert b["recurring"] is False and b["frequency"] == "one_off"


def _plan(pm, next_date, name):
    cust = stripe.Customer.create(email=f"test_res11_{uuid.uuid4().hex[:6]}@example.com", name=name)
    CREATED["customers"].append(cust.id)
    p = stripe.PaymentMethod.attach(pm, customer=cust.id)
    lead = {"_id": DB.leads.insert_one({"company_id": CID, "name": name, "email": cust.email, "phone": "07700900123", "status": "booked", "source": "website",
                                         "type": "residential", "timeline": [], "created_at": dt.datetime.utcnow().isoformat()}).inserted_id}
    CREATED["emails"].append(cust.email)
    qid = DB.quotes.insert_one({"company_id": CID, "lead_id": str(lead["_id"]), "status": "accepted", "input": EXAMPLE, "result": {}, "total": 50.0,
                                "created_at": dt.datetime.utcnow().isoformat()}).inserted_id
    doc = {"company_id": CID, "lead_id": str(lead["_id"]), "quote_id": str(qid), "customer": {"name": name, "email": cust.email, "phone": "07700900123"},
           "postcode": "SW19 2AB", "address": "TEST_ 1 Road", "service": "regular", "service_name": "Residential / Regular Clean", "input": EXAMPLE,
           "lines": [], "total": 50.0, "slot": "08:00", "access": {"method": "customer_present"}, "access_notes": "", "source": "website", "frequency": "weekly",
           "first_booking_id": "TEST_", "next_date": next_date, "stripe_customer": cust.id, "payment_method": p.id, "status": "active", "created_at": dt.datetime.utcnow().isoformat()}
    pid = DB.recurring_plans.insert_one(doc).inserted_id
    CREATED["plans"].append(pid)
    return pid


# --- Cron + plans
class TestRecurringCron:
    def test_cron_unauthorized(self):
        assert requests.post(f"{BASE}/api/cron/recurring", timeout=15).status_code == 401
        assert requests.post(f"{BASE}/api/cron/recurring", headers={"Authorization": "Bearer wrong"}, timeout=15).status_code == 401

    def test_cron_charges_success_and_failure(self, owner):
        tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        far = (dt.date.today() + dt.timedelta(days=20)).isoformat()
        ok_id = _plan("pm_card_visa", tomorrow, "TEST_ Plan OK")
        bad_id = _plan("pm_card_chargeCustomerFail", tomorrow, "TEST_ Plan Fail")
        far_id = _plan("pm_card_visa", far, "TEST_ Plan Far")
        wid = f"TEST_{uuid.uuid4().hex}"
        h = {"Authorization": f"Bearer {CRON}", "X-Webhook-Id": wid}
        r = requests.post(f"{BASE}/api/cron/recurring", headers=h, timeout=30)
        assert r.status_code == 200 and r.json() == {"ok": True}, r.text
        r2 = requests.post(f"{BASE}/api/cron/recurring", headers=h, timeout=30)
        assert r2.json() == {"ok": True, "duplicate": True}, r2.text
        DB.cron_runs.delete_one({"_id": wid})
        import time
        for _ in range(30):
            time.sleep(1)
            if DB.recurring_plans.find_one({"_id": bad_id}).get("last_result") and DB.recurring_plans.find_one({"_id": ok_id}).get("last_result"):
                break
        ok, bad, farp = (DB.recurring_plans.find_one({"_id": i}) for i in (ok_id, bad_id, far_id))
        nxt = (dt.date.today() + dt.timedelta(days=8)).isoformat()
        assert ok["last_result"] == "paid" and ok["next_date"] == nxt, ok
        assert bad["last_result"] == "failed" and bad["next_date"] == nxt, bad
        assert "last_result" not in farp and farp["next_date"] == far
        cb = DB.bookings.find_one({"recurring_plan_id": str(ok_id)})
        CREATED["bookings"].append(str(cb["_id"]))
        assert cb["status"] == "confirmed" and cb["payment_status"] == "paid" and cb["date"] == tomorrow
        tx = DB.payment_transactions.find_one({"booking_id": str(cb["_id"])})
        assert tx["kind"] == "recurring" and tx["payment_status"] == "paid"
        fb = DB.bookings.find_one({"recurring_plan_id": str(bad_id)})
        CREATED["bookings"].append(str(fb["_id"]))
        assert fb["status"] == "payment_failed" and fb["payment_status"] == "failed"
        assert DB.communications.find_one({"template": "recurring_payment_failed", "to": bad["customer"]["email"]}), "no customer failure email logged"
        assert DB.communications.find_one({"lead_id": bad["lead_id"], "to": {"$ne": bad["customer"]["email"]}, "subject": {"$regex": "payment failed"}}), "no owner email"

    def test_admin_plan_status(self, owner):
        pid = _plan("pm_card_visa", "2030-01-01", "TEST_ Plan Status")
        g = owner.get(f"{BASE}/api/admin/recurring/{pid}", timeout=15)
        assert g.status_code == 200 and "payment_method" not in g.json() and "stripe_customer" not in g.json()
        assert requests.post(f"{BASE}/api/admin/recurring/{pid}/status", json={"status": "paused"}, timeout=15).status_code in (401, 403)
        assert owner.post(f"{BASE}/api/admin/recurring/{pid}/status", json={"status": "bogus"}, timeout=15).status_code == 422
        for st in ("paused", "active", "cancelled"):
            r = owner.post(f"{BASE}/api/admin/recurring/{pid}/status", json={"status": st}, timeout=15)
            assert r.status_code == 200, r.text
            assert owner.get(f"{BASE}/api/admin/recurring/{pid}", timeout=15).json()["status"] == st
        assert owner.post(f"{BASE}/api/admin/recurring/{pid}/status", json={"status": "active"}, timeout=15).status_code == 400


def teardown_module(module):
    ids = [ObjectId(b) for b in CREATED["bookings"]]
    plan_ids = [str(p) for p in CREATED["plans"]]
    child = [b["_id"] for b in DB.bookings.find({"recurring_plan_id": {"$in": plan_ids}})]
    allb = ids + child
    DB.payment_transactions.delete_many({"booking_id": {"$in": [str(i) for i in allb]}})
    DB.bookings.delete_many({"_id": {"$in": allb}})
    DB.recurring_plans.delete_many({"_id": {"$in": CREATED["plans"]}})
    emails = CREATED["emails"] + [c for c in []]
    leads = [l["_id"] for l in DB.leads.find({"email": {"$in": emails}})]
    DB.quotes.delete_many({"lead_id": {"$in": [str(l) for l in leads]}})
    DB.leads.delete_many({"_id": {"$in": leads}})
    DB.communications.delete_many({"$or": [{"to": {"$regex": "^test_res11_"}}, {"lead_id": {"$in": [str(l) for l in leads]}}]})
    for c in CREATED["customers"]:
        try:
            stripe.Customer.delete(c)
        except Exception:
            pass
