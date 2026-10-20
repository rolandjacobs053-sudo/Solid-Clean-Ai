"""Iteration 12: removed extras, owner price changes flow to quotes, residential summary on booking + emails,
cancel cascade to recurring plan, resume roll-forward, robust _charge_visit (advance on existing visit / finalize failure),
SO- reference prefix, monthly anchor day. Creates TEST_ data and cleans it up; restores Settings."""
import copy
import datetime as dt
import os
import sys
import time
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
CREATED = {"bookings": [], "plans": [], "emails": [], "customers": [], "leads": [], "quotes": []}
REMOVED = {"garden_furniture", "wall_washing", "mattress", "sofa", "rug", "curtains"}
EXAMPLE = {"service": "regular", "property_type": "house", "bedrooms": 3, "bathrooms": 2, "living_rooms": 1, "frequency": "weekly",
           "people": "3_4", "pets": "yes", "last_cleaned": "1_3_months", "tasks": ["general", "kitchen", "beds", "ironing", "other"],
           "task_qty": {"beds": 3, "ironing": 2}, "extras": ["oven"], "other_request": "TEST_ please clean the fish tank glass"}
TODAY = dt.date.today()


@pytest.fixture(scope="module")
def owner():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=OWNER, timeout=20)
    assert r.status_code == 200, r.text
    return s


def _prev(**kw):
    return requests.post(f"{PUB}/quote/preview", json={**EXAMPLE, **kw}, timeout=20).json()


# --- Extras removed
class TestExtrasRemoved:
    def test_config_extras(self):
        p = requests.get(f"{PUB}/config", timeout=15).json()["pricing"]
        keys = {e["key"] for e in p["extras"]}
        names = " ".join(e["name"].lower() for e in p["extras"])
        assert not keys & REMOVED, keys
        for w in ("garden", "wall", "mattress", "sofa", "upholster", "rug", "curtain"):
            assert w not in names
        assert len(keys) == 14, keys
        for s in p["services"]:
            assert not set(s.get("extras") or []) & REMOVED

    def test_admin_settings_extras(self, owner):
        s = owner.get(f"{BASE}/api/admin/settings", timeout=15).json()
        assert not {e["key"] for e in s["pricing"]["extras"]} & REMOVED

    def test_per_item_extras_still_work(self):
        d = _prev(frequency="one_off", extras=["blinds", "windows", "balcony"], extra_qty={"blinds": 3, "windows": 4, "balcony": 2})
        labels = {l["label"]: l["amount"] for l in d["lines"]}
        assert any(k.startswith("Blinds cleaning × 3") for k in labels), labels
        assert any(k.startswith("Interior windows × 4") for k in labels), labels
        assert any(k.startswith("Balcony / patio × 2") for k in labels), labels

    def test_removed_extra_ignored_in_quote(self):
        a = _prev(frequency="one_off", extras=["oven"])["total"]
        b = _prev(frequency="one_off", extras=["oven", "sofa", "rug", "mattress"])["total"]
        assert a == b


# --- Owner price changes flow through
class TestOwnerPriceChange:
    def test_blinds_and_weekly_discount_change(self, owner):
        orig = owner.get(f"{BASE}/api/admin/settings", timeout=15).json()
        body = {k: copy.deepcopy(orig[k]) for k in ("business", "pricing", "availability", "knowledge_base")}
        base_q = _prev(frequency="one_off", extras=["blinds"], extra_qty={"blinds": 2})
        weekly_q = _prev()
        blinds_old = next(e for e in body["pricing"]["extras"] if e["key"] == "blinds")["price"]
        try:
            next(e for e in body["pricing"]["extras"] if e["key"] == "blinds")["price"] = blinds_old + 3
            next(f for f in body["pricing"]["residential"]["frequencies"] if f["key"] == "weekly")["discount"] = 25
            r = owner.put(f"{BASE}/api/admin/settings", json=body, timeout=20)
            assert r.status_code == 200, r.text
            cfg = requests.get(f"{PUB}/config", timeout=15).json()["pricing"]
            assert next(e for e in cfg["extras"] if e["key"] == "blinds")["price"] == blinds_old + 3
            assert next(f for f in cfg["residential"]["frequencies"] if f["key"] == "weekly")["discount"] == 25
            nq = _prev(frequency="one_off", extras=["blinds"], extra_qty={"blinds": 2})
            assert round(nq["total"] - base_q["total"], 2) == 6.0, (nq, base_q)
            nw = _prev()
            assert any(l["label"] == "Weekly cleaning discount (25%)" for l in nw["lines"]), nw["lines"]
            assert nw["total"] < weekly_q["total"]
        finally:
            r = owner.put(f"{BASE}/api/admin/settings", json={k: orig[k] for k in ("business", "pricing", "availability", "knowledge_base")}, timeout=20)
            assert r.status_code == 200
        assert _prev()["total"] == weekly_q["total"]


def _slot():
    d = TODAY + dt.timedelta(days=10)
    for _ in range(30):
        r = requests.get(f"{PUB}/availability", params={"date": d.isoformat()}, timeout=15)
        js = r.json() if r.status_code == 200 else []
        slots = js.get("slots", js) if isinstance(js, dict) else js
        if slots:
            s = slots[0]
            return d.isoformat(), s["slot"] if isinstance(s, dict) else s
        d += dt.timedelta(days=1)
    pytest.skip("no slot")


# --- Booking residential summary
class TestResidentialSummary:
    def test_booking_has_residential_summary(self):
        email = f"test_res12_{uuid.uuid4().hex[:6]}@example.com"
        CREATED["emails"].append(email)
        day, slot = _slot()
        pol = {p["key"]: p["published_version"] for p in requests.get(f"{PUB}/config", timeout=15).json().get("policies", []) if p.get("require_acceptance")}
        body = {"quote": {**EXAMPLE, "postcode": "SW19 2AB", "address": "TEST_ 1 Test Road"}, "contact": {"name": "TEST_ Res12", "email": email, "phone": "07700900123"},
                "date": day, "slot": slot, "access": {"method": "customer_present"}, "accepted_policies": pol, "pay_terms_accepted": True,
                "auto_charge_consent": True, "tip": 0, "origin_url": BASE}
        r = requests.post(f"{PUB}/bookings", json=body, timeout=40)
        assert r.status_code == 200, r.text
        CREATED["bookings"].append(r.json()["booking_id"])
        b = DB.bookings.find_one({"_id": ObjectId(r.json()["booking_id"])})
        res = b["residential"]
        assert res["frequency"] == "Weekly cleaning" and res["people"] == "3-4 people" and res["pets"] == "yes"
        assert res["last_cleaned"] == "1-3 months ago"
        assert res["other_request"] == "TEST_ please clean the fish tank glass"
        assert "Making beds and changing bed linen × 3" in res["services"] and "Ironing clothes × 2" in res["services"]
        assert "General house cleaning" in res["services"]


def _plan(pm, next_date, name, frequency="weekly", anchor=0, status="active", with_quote=True, first_booking_id="TEST_"):
    cust = stripe.Customer.create(email=f"test_res12_{uuid.uuid4().hex[:6]}@example.com", name=name)
    CREATED["customers"].append(cust.id)
    p = stripe.PaymentMethod.attach(pm, customer=cust.id)
    lead = DB.leads.insert_one({"company_id": CID, "name": name, "email": cust.email, "phone": "07700900123", "status": "booked", "source": "website",
                                "type": "residential", "timeline": [], "created_at": dt.datetime.utcnow().isoformat()}).inserted_id
    CREATED["leads"].append(lead)
    CREATED["emails"].append(cust.email)
    qid = None
    if with_quote:
        qid = str(DB.quotes.insert_one({"company_id": CID, "lead_id": str(lead), "status": "accepted", "input": EXAMPLE, "result": {}, "total": 50.0,
                                        "created_at": dt.datetime.utcnow().isoformat()}).inserted_id)
    res = {"frequency": "Weekly cleaning", "people": "3-4 people", "last_cleaned": "1-3 months ago", "pets": "yes",
           "other_request": "TEST_ fish tank", "services": ["General house cleaning", "Ironing clothes × 2"]}
    doc = {"company_id": CID, "lead_id": str(lead), "quote_id": qid, "customer": {"name": name, "email": cust.email, "phone": "07700900123"},
           "postcode": "SW19 2AB", "address": "TEST_ 1 Road", "service": "regular", "service_name": "Residential / Regular Clean", "input": EXAMPLE,
           "lines": [], "total": 50.0, "slot": "08:00", "access": {"method": "customer_present"}, "access_notes": "", "source": "website", "frequency": frequency,
           "residential": res, "first_booking_id": first_booking_id, "anchor_day": anchor, "next_date": next_date, "stripe_customer": cust.id,
           "payment_method": p.id, "status": status, "created_at": dt.datetime.utcnow().isoformat()}
    pid = DB.recurring_plans.insert_one(doc).inserted_id
    CREATED["plans"].append(pid)
    return pid


def _run_cron():
    wid = f"TEST_{uuid.uuid4().hex}"
    r = requests.post(f"{BASE}/api/cron/recurring", headers={"Authorization": f"Bearer {CRON}", "X-Webhook-Id": wid}, timeout=30)
    DB.cron_runs.delete_one({"_id": wid})
    assert r.status_code == 200 and r.json() == {"ok": True}, r.text


# --- Cron robustness
class TestChargeVisit:
    def test_cron_existing_visit_failed_finalize_monthly_anchor(self):
        tomorrow = (TODAY + dt.timedelta(days=1)).isoformat()
        ok_id = _plan("pm_card_visa", tomorrow, "TEST_ Plan12 OK")
        exist_id = _plan("pm_card_visa", tomorrow, "TEST_ Plan12 Exists")
        nofin_id = _plan("pm_card_visa", tomorrow, "TEST_ Plan12 NoQuote", with_quote=False)
        mon_id = _plan("pm_card_visa", tomorrow, "TEST_ Plan12 Monthly", frequency="monthly", anchor=31)
        pre = DB.bookings.insert_one({"company_id": CID, "recurring_plan_id": str(exist_id), "date": tomorrow, "slot": "08:00", "status": "confirmed",
                                      "customer": {"name": "TEST_ x", "email": "test_res12_x@example.com", "phone": "1"}, "service_name": "TEST_"}).inserted_id
        CREATED["bookings"].append(str(pre))
        _run_cron()
        ids = (ok_id, exist_id, nofin_id, mon_id)
        for _ in range(40):
            time.sleep(1)
            if all(DB.recurring_plans.find_one({"_id": i}).get("last_run_at") for i in ids):
                break
        nxt = (TODAY + dt.timedelta(days=8)).isoformat()
        ok, ex, nf, mon = (DB.recurring_plans.find_one({"_id": i}) for i in ids)
        assert ok["next_date"] == nxt and ok["last_result"] == "paid", ok
        assert ex["next_date"] == nxt, ex
        assert DB.bookings.count_documents({"recurring_plan_id": str(exist_id)}) == 1
        assert nf["next_date"] == nxt, nf  # finalize failed (no quote) but plan advanced
        t = dt.date.fromisoformat(tomorrow)
        import calendar
        m, y = t.month % 12 + 1, t.year + (t.month == 12)
        assert mon["next_date"] == dt.date(y, m, min(31, calendar.monthrange(y, m)[1])).isoformat(), mon
        cb = DB.bookings.find_one({"recurring_plan_id": str(ok_id)})
        assert cb["reference"].startswith("SO-"), cb["reference"]
        assert cb["status"] == "confirmed"
        conf = DB.communications.find_one({"lead_id": ok["lead_id"], "template": "booking_confirmation", "channel": "email"}) or \
            DB.communications.find_one({"lead_id": ok["lead_id"], "template": "booking_confirmation", "to": ok["customer"]["email"]})
        assert conf and "Ironing clothes × 2" in (conf.get("body") or conf.get("text") or str(conf)), conf
        assert "TEST_ fish tank" in str(conf)
        owner_mail = DB.communications.find_one({"lead_id": ok["lead_id"], "subject": {"$regex": "^New booking"}})
        assert owner_mail and "Services:" in str(owner_mail) and "TEST_ fish tank" in str(owner_mail)


class TestNextVisitUnit:
    def test_monthly_anchor_roundtrip(self):
        sys.path.insert(0, "/app/backend")
        os.environ.setdefault("MONGO_URL", ENV["MONGO_URL"])
        os.environ.setdefault("DB_NAME", ENV["DB_NAME"])
        for k, v in ENV.items():
            os.environ.setdefault(k, v or "")
        from routes_recurring import next_visit
        assert next_visit("2026-10-31", "monthly", 31) == "2026-11-30"
        assert next_visit("2026-11-30", "monthly", 31) == "2026-12-31"
        assert next_visit("2027-01-31", "monthly", 31) == "2027-02-28"
        assert next_visit("2027-02-28", "monthly", 31) == "2027-03-31"
        assert next_visit("2026-12-15", "monthly", 15) == "2027-01-15"
        assert next_visit("2026-10-20", "fortnightly") == "2026-11-03"


# --- Resume / cancel cascade
class TestPlanStatusFixes:
    def test_resume_rolls_forward(self, owner):
        past = (TODAY - dt.timedelta(days=20)).isoformat()
        pid = _plan("pm_card_visa", past, "TEST_ Plan12 Resume", status="paused")
        r = owner.post(f"{BASE}/api/admin/recurring/{pid}/status", json={"status": "active"}, timeout=15)
        assert r.status_code == 200, r.text
        p = DB.recurring_plans.find_one({"_id": pid})
        assert p["status"] == "active" and p["next_date"] > TODAY.isoformat(), p["next_date"]
        assert (dt.date.fromisoformat(p["next_date"]) - dt.date.fromisoformat(past)).days % 7 == 0

    def _first(self, name, payment_status="paid"):
        lead = DB.leads.insert_one({"company_id": CID, "name": name, "email": "test_res12_c@example.com", "phone": "1", "status": "booked",
                                    "timeline": [], "created_at": dt.datetime.utcnow().isoformat()}).inserted_id
        CREATED["leads"].append(lead)
        day = (TODAY + dt.timedelta(days=12)).isoformat()
        bid = DB.bookings.insert_one({"company_id": CID, "lead_id": str(lead), "date": day, "slot": "08:00", "status": "confirmed", "payment_status": payment_status,
                                      "total": 100.0, "deposit_amount": 100.0, "balance_due": 0, "tip": 0, "reference": "SO-TEST",
                                      "customer": {"name": name, "email": "test_res12_c@example.com", "phone": "1"}, "service_name": "TEST_ Residential",
                                      "postcode": "SW19", "recurring": True, "frequency": "weekly"}).inserted_id
        CREATED["bookings"].append(str(bid))
        pid = _plan("pm_card_visa", "2030-01-07", name, first_booking_id=str(bid))
        DB.bookings.update_one({"_id": bid}, {"$set": {"recurring_plan_id": str(pid)}})
        return bid, pid

    def test_patch_cancel_cascades(self, owner):
        bid, pid = self._first("TEST_ Plan12 CancelPatch")
        r = owner.patch(f"{BASE}/api/admin/bookings/{bid}", json={"status": "cancelled"}, timeout=15)
        assert r.status_code == 200, r.text
        assert DB.recurring_plans.find_one({"_id": pid})["status"] == "cancelled"

    def test_cancel_refund_cascades(self, owner):
        bid, pid = self._first("TEST_ Plan12 CancelRefund")
        r = owner.post(f"{BASE}/api/admin/bookings/{bid}/cancel-refund", json={"amount": 100.0, "note": "TEST_"}, timeout=15)
        assert r.status_code == 200, r.text
        assert DB.recurring_plans.find_one({"_id": pid})["status"] == "cancelled"

    def test_child_cancel_does_not_cancel_plan(self, owner):
        bid, pid = self._first("TEST_ Plan12 Child")
        DB.recurring_plans.update_one({"_id": pid}, {"$set": {"first_booking_id": "other"}})
        r = owner.patch(f"{BASE}/api/admin/bookings/{bid}", json={"status": "cancelled"}, timeout=15)
        assert r.status_code == 200
        assert DB.recurring_plans.find_one({"_id": pid})["status"] == "active"


def teardown_module(module):
    plan_ids = [str(p) for p in CREATED["plans"]]
    child = [b["_id"] for b in DB.bookings.find({"recurring_plan_id": {"$in": plan_ids}})]
    allb = [ObjectId(b) for b in CREATED["bookings"]] + child
    DB.payment_transactions.delete_many({"booking_id": {"$in": [str(i) for i in allb]}})
    DB.bookings.delete_many({"_id": {"$in": allb}})
    DB.recurring_plans.delete_many({"_id": {"$in": CREATED["plans"]}})
    leads = CREATED["leads"] + [l["_id"] for l in DB.leads.find({"email": {"$in": CREATED["emails"]}})]
    DB.quotes.delete_many({"lead_id": {"$in": [str(l) for l in leads]}})
    DB.communications.delete_many({"$or": [{"to": {"$regex": "^test_res12_"}}, {"lead_id": {"$in": [str(l) for l in leads]}}]})
    DB.leads.delete_many({"_id": {"$in": leads}})
    for c in CREATED["customers"]:
        try:
            stripe.Customer.delete(c)
        except Exception:
            pass
