"""Iteration 13: Regular Clients (GET /api/admin/recurring + status), customer feedback flow
(complete booking -> token+email, public feedback info/submit, consent/hidden filtering on public reviews, admin hide).
Seeds TEST_ data in Mongo and deletes it on teardown."""
import datetime as dt
import os
import uuid

import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
PUB = f"{BASE}/api/public/solid-clean"
OWNER = {"email": "admin@solidcleanltd.com", "password": "SolidClean#2026"}
ENV = dotenv_values("/app/backend/.env")
DB = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
CID = "6acb2a20e5d23531c955e49b"
TODAY = dt.date.today()
C = {"leads": [], "bookings": [], "plans": [], "users": []}


def _lead(tag):
    lid = DB.leads.insert_one({"company_id": CID, "name": f"TEST_{tag} Smith", "email": f"test_{tag}@example.com", "phone": "07700900000",
                               "status": "booked", "timeline": [], "created_at": dt.datetime.utcnow().isoformat()}).inserted_id
    C["leads"].append(lid)
    return str(lid)


def _booking(tag, status="confirmed", plan_id=None, date=None, assigned=None, payment="paid"):
    lid = _lead(tag)
    doc = {"company_id": CID, "lead_id": lid, "customer": {"name": f"TEST_{tag} Smith", "email": f"test_{tag}@example.com", "phone": "07700900000"},
           "postcode": "SW11 5RT", "service": "regular", "service_name": "Residential / Regular Clean", "input": {}, "total": 60.0,
           "date": date or (TODAY + dt.timedelta(days=3)).isoformat(), "slot": "10:00", "status": status, "payment_status": payment,
           "source": "website", "created_at": dt.datetime.utcnow().isoformat()}
    if plan_id:
        doc["recurring_plan_id"] = plan_id
    if assigned:
        doc["assigned_to"] = assigned
    bid = DB.bookings.insert_one(doc).inserted_id
    C["bookings"].append(bid)
    return str(bid), lid


def _plan(tag, freq, total, status="active", card=True):
    lid = _lead(tag)
    doc = {"company_id": CID, "lead_id": lid, "customer": {"name": f"TEST_{tag} Jones", "email": f"test_{tag}@example.com", "phone": "07700900001"},
           "postcode": "SW11 5RT", "service": "regular", "service_name": "Residential / Regular Clean", "total": total, "frequency": freq,
           "next_date": (TODAY + dt.timedelta(days=5)).isoformat(), "slot": "09:00", "status": status, "last_result": None, "anchor_day": 1,
           "stripe_customer": "cus_TEST", "created_at": dt.datetime.utcnow().isoformat()}
    if card:
        doc["payment_method"] = "pm_TEST"
    pid = DB.recurring_plans.insert_one(doc).inserted_id
    C["plans"].append(pid)
    return str(pid)


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    rev_ids = [b.get("review_id") for b in DB.bookings.find({"_id": {"$in": C["bookings"]}})]
    DB.reviews.delete_many({"booking_id": {"$in": [str(b) for b in C["bookings"]]}})
    DB.reviews.delete_many({"_id": {"$in": [ObjectId(r) for r in rev_ids if r]}})
    DB.communications.delete_many({"lead_id": {"$in": [str(x) for x in C["leads"]]}})
    DB.bookings.delete_many({"_id": {"$in": C["bookings"]}})
    DB.recurring_plans.delete_many({"_id": {"$in": C["plans"]}})
    DB.leads.delete_many({"_id": {"$in": C["leads"]}})
    DB.users.delete_many({"_id": {"$in": C["users"]}})


@pytest.fixture(scope="module")
def owner():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=OWNER, timeout=20)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def staff(owner):
    email = f"test_cleaner_{uuid.uuid4().hex[:6]}@example.com"
    r = owner.post(f"{BASE}/api/admin/staff", json={"name": "TEST_Cleaner13", "email": email, "password": "Testpass123", "job_role": "Cleaner"}, timeout=20)
    assert r.status_code == 200, r.text
    u = DB.users.find_one({"email": email})
    C["users"].append(u["_id"])
    s = requests.Session()
    assert s.post(f"{BASE}/api/auth/login", json={"email": email, "password": "Testpass123"}, timeout=20).status_code == 200
    return s, str(u["_id"])


# --- Regular clients list
class TestRegularClients:
    def test_list_fields_and_no_secrets(self, owner):
        pid = _plan("rc_w", "weekly", 60.0)
        _booking("rc_w_visit", status="completed", plan_id=pid, date=(TODAY - dt.timedelta(days=2)).isoformat())
        r = owner.get(f"{BASE}/api/admin/recurring", timeout=20)
        assert r.status_code == 200, r.text
        row = next(p for p in r.json() if p["id"] == pid)
        assert "payment_method" not in row and "stripe_customer" not in row and "_id" not in row
        assert row["card_saved"] is True
        assert row["frequency"] == "weekly" and row["total"] == 60.0 and row["status"] == "active"
        assert row["visits"] == 1
        assert row["last_visit"]["status"] == "completed" and row["last_visit"]["payment_status"] == "paid"
        for k in ("customer", "next_date", "slot", "last_result"):
            assert k in row

    def test_no_card_flag_and_no_visits(self, owner):
        pid = _plan("rc_nocard", "monthly", 100.0, status="paused", card=False)
        row = next(p for p in owner.get(f"{BASE}/api/admin/recurring", timeout=20).json() if p["id"] == pid)
        assert row["card_saved"] is False and row["visits"] == 0 and row["last_visit"] is None

    def test_staff_forbidden(self, staff):
        s, _ = staff
        assert s.get(f"{BASE}/api/admin/recurring", timeout=20).status_code == 403

    def test_pause_resume_cancel(self, owner):
        pid = _plan("rc_f", "fortnightly", 80.0)
        assert owner.post(f"{BASE}/api/admin/recurring/{pid}/status", json={"status": "paused"}, timeout=20).status_code == 200
        assert DB.recurring_plans.find_one({"_id": ObjectId(pid)})["status"] == "paused"
        assert owner.post(f"{BASE}/api/admin/recurring/{pid}/status", json={"status": "active"}, timeout=20).status_code == 200
        assert DB.recurring_plans.find_one({"_id": ObjectId(pid)})["status"] == "active"
        assert owner.post(f"{BASE}/api/admin/recurring/{pid}/status", json={"status": "cancelled"}, timeout=20).status_code == 200
        row = next(p for p in owner.get(f"{BASE}/api/admin/recurring", timeout=20).json() if p["id"] == pid)
        assert row["status"] == "cancelled"
        assert owner.post(f"{BASE}/api/admin/recurring/{pid}/status", json={"status": "active"}, timeout=20).status_code == 400

    def test_resume_without_card_400(self, owner):
        pid = _plan("rc_nocard2", "weekly", 50.0, status="paused", card=False)
        assert owner.post(f"{BASE}/api/admin/recurring/{pid}/status", json={"status": "active"}, timeout=20).status_code == 400


# --- Feedback flow
class TestFeedback:
    state = {}

    def test_complete_sets_token_and_email(self, owner):
        bid, lid = _booking("fb1")
        r = owner.patch(f"{BASE}/api/admin/bookings/{bid}", json={"status": "completed"}, timeout=30)
        assert r.status_code == 200, r.text
        b = DB.bookings.find_one({"_id": ObjectId(bid)})
        assert b["status"] == "completed" and b.get("feedback_token")
        comm = DB.communications.find_one({"lead_id": lid, "template": "feedback_review_request"})
        assert comm, "feedback email not logged"
        assert comm["subject"] == "How did we do?"
        assert comm["link"][1] == f"https://{BASE.split('://')[1]}/feedback/{bid}?t={b['feedback_token']}", comm["link"]
        self.state.update(bid=bid, lid=lid, t=b["feedback_token"])

    def test_info_and_invalid_token(self):
        s = self.state
        r = requests.get(f"{PUB}/feedback/{s['bid']}", params={"t": s["t"]}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["first_name"] == "TEST_fb1" and d["suggested_name"] == "TEST_fb1 S." and d["done"] is False
        assert requests.get(f"{PUB}/feedback/{s['bid']}", params={"t": "wrong"}, timeout=20).status_code == 404
        assert requests.post(f"{PUB}/feedback/{s['bid']}", json={"t": "wrong", "rating": 5, "display_name": "X"}, timeout=20).status_code == 404

    def test_validation(self):
        s = self.state
        assert requests.post(f"{PUB}/feedback/{s['bid']}", json={"t": s["t"], "rating": 6, "display_name": "X"}, timeout=20).status_code == 422
        assert requests.post(f"{PUB}/feedback/{s['bid']}", json={"t": s["t"], "rating": 0, "display_name": "X"}, timeout=20).status_code == 422
        assert requests.post(f"{PUB}/feedback/{s['bid']}", json={"t": s["t"], "rating": 5, "display_name": ""}, timeout=20).status_code == 422

    def test_submit_consented_5star(self):
        s = self.state
        r = requests.post(f"{PUB}/feedback/{s['bid']}", json={"t": s["t"], "rating": 5, "text": "TEST_ great clean", "display_name": "TEST_Fb One",
                                                                "publish_consent": True}, timeout=20)
        assert r.status_code == 200, r.text
        rv = DB.reviews.find_one({"booking_id": s["bid"]})
        assert rv["source"] == "customer_feedback" and rv["platform"] == "website" and rv["publish_consent"] is True and rv["status"] == "new"
        assert rv["company_id"] == CID
        s["rid"] = str(rv["_id"])
        assert DB.communications.find_one({"lead_id": s["lid"], "template": "owner_notification"})
        r2 = requests.post(f"{PUB}/feedback/{s['bid']}", json={"t": s["t"], "rating": 4, "display_name": "X"}, timeout=20)
        assert r2.status_code == 409
        assert requests.get(f"{PUB}/feedback/{s['bid']}", params={"t": s["t"]}, timeout=20).json()["done"] is True
        assert DB.reviews.count_documents({"booking_id": s["bid"]}) == 1

    def test_public_reviews_include_consented(self):
        rows = requests.get(f"{PUB}/reviews", timeout=20).json()
        mine = [r for r in rows if r["author"] == "TEST_Fb One"]
        assert len(mine) == 1 and mine[0]["verified"] is True and mine[0]["rating"] == 5
        assert "booking_id" not in mine[0] and "publish_consent" not in mine[0]

    def test_low_rating_no_consent(self, owner):
        bid, lid = _booking("fb2")
        owner.patch(f"{BASE}/api/admin/bookings/{bid}", json={"status": "completed"}, timeout=30)
        t = DB.bookings.find_one({"_id": ObjectId(bid)})["feedback_token"]
        r = requests.post(f"{PUB}/feedback/{bid}", json={"t": t, "rating": 2, "text": "TEST_ missed kitchen", "display_name": "TEST_Fb Two",
                                                          "publish_consent": False}, timeout=20)
        assert r.status_code == 200, r.text
        rv = DB.reviews.find_one({"booking_id": bid})
        assert rv["status"] == "needs_attention" and rv["publish_consent"] is False
        n = DB.communications.find_one({"lead_id": lid, "template": "owner_notification"})
        assert n and "needs attention" in n["subject"]
        rows = requests.get(f"{PUB}/reviews", timeout=20).json()
        assert not any(r["author"] == "TEST_Fb Two" for r in rows)

    def test_hide_review(self, owner):
        rid = self.state["rid"]
        r = owner.patch(f"{BASE}/api/admin/reviews/{rid}", json={"hidden": True, "hidden_reason": "TEST_ reason"}, timeout=20)
        assert r.status_code == 200
        rv = DB.reviews.find_one({"_id": ObjectId(rid)})
        assert rv["hidden"] is True and rv["hidden_reason"] == "TEST_ reason"
        assert not any(x["author"] == "TEST_Fb One" for x in requests.get(f"{PUB}/reviews", timeout=20).json())
        adm = owner.get(f"{BASE}/api/admin/reviews", timeout=20)
        assert adm.status_code == 200
        assert any(x.get("id") == rid and x.get("hidden") for x in adm.json()["reviews"])
        owner.patch(f"{BASE}/api/admin/reviews/{rid}", json={"hidden": False}, timeout=20)
        assert any(x["author"] == "TEST_Fb One" for x in requests.get(f"{PUB}/reviews", timeout=20).json())


# --- Regression: staff completes own job
class TestStaffComplete:
    def test_staff_own_and_other(self, staff):
        s, uid = staff
        own, _ = _booking("st_own", assigned=uid)
        other, _ = _booking("st_other", assigned=str(ObjectId()))
        assert s.patch(f"{BASE}/api/admin/bookings/{other}", json={"status": "completed"}, timeout=20).status_code == 403
        r = s.patch(f"{BASE}/api/admin/bookings/{own}", json={"status": "completed"}, timeout=30)
        assert r.status_code == 200, r.text
        b = DB.bookings.find_one({"_id": ObjectId(own)})
        assert b["status"] == "completed" and b.get("feedback_token")
