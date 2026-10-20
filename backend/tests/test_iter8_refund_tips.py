"""Iteration 8: unpublished 'complaints' policy, pay_terms_accepted + tip at booking, owner cancel & refund
(refund-quote / cancel-refund), tip request + public tip page API. Seeds TEST_ data in Mongo, cleans up on teardown."""
import datetime as dt
import os
import uuid
from zoneinfo import ZoneInfo

import pytest
import requests
import stripe
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
PUB = f"{BASE}/api/public/solid-clean"
ADM = f"{BASE}/api/admin"
OWNER = {"email": "admin@solidcleanltd.com", "password": "SolidClean#2026"}
ENV = dotenv_values("/app/backend/.env")
DB = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
CID = "6acb2a20e5d23531c955e49b"
stripe.api_key = ENV.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_SECRET_KEY")
LONDON = ZoneInfo("Europe/London")
CREATED = {"bookings": [], "leads": []}


def _now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat()


@pytest.fixture(scope="module")
def owner():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=OWNER, timeout=20)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def cfg():
    return requests.get(f"{PUB}/config", timeout=15).json()


@pytest.fixture(scope="module")
def lead_id():
    lid = DB.leads.insert_one({"company_id": CID, "name": "TEST_ Refund Lead", "email": "delivered@resend.dev", "phone": "07700900111",
                               "status": "booked", "source": "website", "timeline": [], "created_at": _now_iso()}).inserted_id
    CREATED["leads"].append(str(lid))
    return str(lid)


def _seed(lead_id, days, status="confirmed", pay="paid", total=120.0, deposit=None, tip=0, slot="08:00"):
    day = (dt.datetime.now(LONDON).date() + dt.timedelta(days=days)).isoformat()
    doc = {"company_id": CID, "lead_id": lead_id, "quote_id": str(ObjectId()), "customer": {"name": f"TEST_ Refund {days}d", "email": "delivered@resend.dev",
           "phone": "07700900111"}, "postcode": "SW1A 1AA", "service": "regular", "service_name": "Residential / Regular Clean", "total": total,
           "deposit_amount": deposit if deposit is not None else total, "balance_due": total - (deposit if deposit is not None else total),
           "tip": tip, "date": day, "slot": slot, "status": status, "payment_status": pay, "reference": f"TS-{uuid.uuid4().hex[:6].upper()}",
           "source": "website", "created_at": _now_iso()}
    bid = str(DB.bookings.insert_one(doc).inserted_id)
    CREATED["bookings"].append(bid)
    return bid, day


def _expected_pct(day, slot="08:00"):
    start = dt.datetime.fromisoformat(f"{day}T{slot}").replace(tzinfo=LONDON)
    h = (start - dt.datetime.now(dt.timezone.utc)).total_seconds() / 3600
    return 100 if h >= 168 else 50 if h >= 48 else 0


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    ids = CREATED["bookings"]
    DB.payment_transactions.delete_many({"booking_id": {"$in": ids}})
    DB.bookings.delete_many({"_id": {"$in": [ObjectId(i) for i in ids]}})
    names = DB.bookings.find({"customer.name": {"$regex": "^TEST_"}}, {"_id": 1, "lead_id": 1})
    for b in list(names):
        DB.payment_transactions.delete_many({"booking_id": str(b["_id"])})
        CREATED["leads"].append(b.get("lead_id"))
    DB.bookings.delete_many({"customer.name": {"$regex": "^TEST_"}})
    lids = [l for l in CREATED["leads"] if l] + [str(l["_id"]) for l in DB.leads.find({"name": {"$regex": "^TEST_"}}, {"_id": 1})]
    DB.communications.delete_many({"lead_id": {"$in": lids}})
    DB.quotes.delete_many({"lead_id": {"$in": lids}})
    DB.photos.delete_many({"lead_id": {"$in": lids}})
    DB.leads.delete_many({"_id": {"$in": [ObjectId(l) for l in lids]}})


# --- Policies: complaints unpublished, only terms public ---
class TestPolicies:
    def test_config_only_terms(self, cfg):
        keys = [p["key"] for p in cfg["policies"]]
        assert keys == ["terms"], keys
        t = cfg["policies"][0]
        assert t["published_version"] == 2 and t["require_acceptance"] is True
        txt = t["published_content"].lower()
        assert "does not offer refunds" not in txt
        assert "deposit" not in txt, "deposit wording found in terms"

    def test_unpublish_requires_confirm_and_owner(self, owner):
        assert owner.post(f"{ADM}/policies/complaints/unpublish", json={"confirm": False}).status_code == 400
        assert requests.post(f"{ADM}/policies/complaints/unpublish", json={"confirm": True}).status_code in (401, 403)
        rows = {p["key"]: p for p in owner.get(f"{ADM}/policies").json()}
        assert rows["complaints"].get("unpublished") is True


# --- Public booking: pay_terms_accepted + tip ---
def _slot():
    for d in range(3, 60):
        day = (dt.date.today() + dt.timedelta(days=d)).isoformat()
        sl = requests.get(f"{PUB}/availability", params={"date": day}, timeout=15).json().get("slots")
        if sl:
            return day, sl[0]["slot"]
    pytest.skip("no availability")


def _body(cfg, **over):
    day, slot = _slot()
    b = {"quote": {"service": "regular", "property_type": "flat", "bedrooms": 2, "bathrooms": 1, "living_rooms": 1, "condition": "good",
                   "extras": [], "postcode": "SW1A 1AA", "address": "TEST_ 8 Tip Street, London", "furnished": "furnished", "flooring": "carpet", "pets": "no"},
         "contact": {"name": f"TEST_tip_{uuid.uuid4().hex[:5]}", "email": "delivered@resend.dev", "phone": "07700900111"},
         "date": day, "slot": slot, "access": {"method": "customer_present"},
         "accepted_policies": {p["key"]: p["published_version"] for p in cfg["policies"] if p.get("require_acceptance")},
         "pay_terms_accepted": True, "tip": 0, "origin_url": BASE, "source": "website", "photos": []}
    b.update(over)
    return b


class TestBookingPayTerms:
    def test_missing_pay_terms_409(self, cfg):
        b = _body(cfg)
        b.pop("pay_terms_accepted")
        r = requests.post(f"{PUB}/bookings", json=b, timeout=30)
        assert r.status_code == 409 and "Terms" in r.json()["detail"]
        assert requests.post(f"{PUB}/bookings", json=_body(cfg, pay_terms_accepted=False), timeout=30).status_code == 409

    def test_tip_bounds(self, cfg):
        assert requests.post(f"{PUB}/bookings", json=_body(cfg, tip=501), timeout=30).status_code == 422
        assert requests.post(f"{PUB}/bookings", json=_body(cfg, tip=-1), timeout=30).status_code == 422

    def test_booking_with_tip(self, cfg):
        r = requests.post(f"{PUB}/bookings", json=_body(cfg, tip=7.5), timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        CREATED["bookings"].append(d["booking_id"])
        assert "checkout.stripe.com" in d["checkout_url"]
        bk = DB.bookings.find_one({"_id": ObjectId(d["booking_id"])})
        assert bk["tip"] == 7.5 and bk.get("pay_terms_confirmed_at")
        tx = DB.payment_transactions.find_one({"booking_id": d["booking_id"]})
        assert tx["amount"] == round(bk["total"] + 7.5, 2) and tx["tip"] == 7.5
        items = stripe.checkout.Session.list_line_items(tx["session_id"])
        names = [i.description for i in items.data]
        assert "Tip for your cleaning team" in names, names
        assert sum(i.amount_total for i in items.data) == int(round((bk["total"] + 7.5) * 100))

    def test_booking_zero_tip_no_line(self, cfg):
        r = requests.post(f"{PUB}/bookings", json=_body(cfg, tip=0), timeout=60)
        assert r.status_code == 200, r.text
        bid = r.json()["booking_id"]
        CREATED["bookings"].append(bid)
        tx = DB.payment_transactions.find_one({"booking_id": bid})
        items = stripe.checkout.Session.list_line_items(tx["session_id"])
        assert len(items.data) == 1


# --- Owner cancel & refund ---
class TestRefund:
    def test_refund_quote_rules(self, owner, lead_id):
        for days in (10, 4, 1):
            bid, day = _seed(lead_id, days)
            r = owner.get(f"{ADM}/bookings/{bid}/refund-quote")
            assert r.status_code == 200, r.text
            q = r.json()
            exp = _expected_pct(day)
            assert q["rule_percent"] == exp, (days, q)
            assert q["paid"] == 120 and q["suggested"] == round(120 * exp / 100, 2)

    def test_refund_quote_with_tip_and_deposit(self, owner, lead_id):
        bid, day = _seed(lead_id, 4, tip=10)
        q = owner.get(f"{ADM}/bookings/{bid}/refund-quote").json()
        assert q["paid"] == 130 and q["suggested"] == round(120 * _expected_pct(day) / 100 + 10, 2), q
        bid, day = _seed(lead_id, 10, pay="deposit_paid", deposit=60)
        q = owner.get(f"{ADM}/bookings/{bid}/refund-quote").json()
        assert q["service_paid"] == 60 and q["suggested"] == 60, q

    def test_refund_not_allowed_for_unpaid_or_completed(self, owner, lead_id):
        bid, _ = _seed(lead_id, 10, pay="due")
        assert owner.get(f"{ADM}/bookings/{bid}/refund-quote").status_code == 400
        assert owner.post(f"{ADM}/bookings/{bid}/cancel-refund", json={"amount": 0}).status_code == 400
        bid, _ = _seed(lead_id, -2, status="completed")
        assert owner.get(f"{ADM}/bookings/{bid}/refund-quote").status_code == 400

    def test_refund_owner_only(self, lead_id):
        bid, _ = _seed(lead_id, 10)
        assert requests.get(f"{ADM}/bookings/{bid}/refund-quote").status_code in (401, 403)
        assert requests.post(f"{ADM}/bookings/{bid}/cancel-refund", json={"amount": 1}).status_code in (401, 403)

    def test_cancel_refund_flow(self, owner, lead_id):
        bid, day = _seed(lead_id, 4)
        assert owner.post(f"{ADM}/bookings/{bid}/cancel-refund", json={"amount": 120.01}).status_code == 400
        assert owner.post(f"{ADM}/bookings/{bid}/cancel-refund", json={"amount": -1}).status_code == 422
        r = owner.post(f"{ADM}/bookings/{bid}/cancel-refund", json={"amount": 80, "note": "TEST goodwill"})
        assert r.status_code == 200, r.text
        ref = r.json()
        assert ref["amount"] == 80 and ref["status"] == "to_issue_in_stripe" and ref["note"] == "TEST goodwill"
        assert ref["rule_percent"] == _expected_pct(day) and ref["suggested"] == 60
        bk = DB.bookings.find_one({"_id": ObjectId(bid)})
        assert bk["status"] == "cancelled" and bk["refund"]["amount"] == 80 and bk["refund"]["notice_hours"] > 0
        comm = DB.communications.find_one({"lead_id": lead_id, "template": "booking_cancelled"}, sort=[("created_at", -1)])
        assert comm and "£80.00" in comm.get("body", comm.get("text", str(comm)))
        assert owner.post(f"{ADM}/bookings/{bid}/cancel-refund", json={"amount": 0}).status_code == 400

    def test_cancel_refund_zero(self, owner, lead_id):
        bid, _ = _seed(lead_id, 1)
        r = owner.post(f"{ADM}/bookings/{bid}/cancel-refund", json={"amount": 0})
        assert r.status_code == 200 and r.json()["rule_percent"] == 0

    def test_plain_cancel_still_works_for_due(self, owner, lead_id):
        bid, _ = _seed(lead_id, 10, pay="due")
        r = owner.patch(f"{ADM}/bookings/{bid}", json={"status": "cancelled"})
        assert r.status_code == 200
        assert DB.bookings.find_one({"_id": ObjectId(bid)})["status"] == "cancelled"


# --- Tip request + public tip API ---
class TestTips:
    def test_tip_request_requires_completed(self, owner, lead_id):
        bid, _ = _seed(lead_id, 10)
        assert owner.post(f"{ADM}/bookings/{bid}/tip-request").status_code == 400
        assert requests.post(f"{ADM}/bookings/{bid}/tip-request").status_code in (401, 403)

    def test_tip_request_and_public_page_api(self, owner, lead_id):
        bid, _ = _seed(lead_id, -1, status="completed", tip=5)
        r = owner.post(f"{ADM}/bookings/{bid}/tip-request")
        assert r.status_code == 200, r.text
        d = r.json()
        assert f"/tip/{bid}?t=" in d["url"] and d["url"].startswith("https://") and "email_status" in d
        token = d["url"].split("?t=")[1]
        # second request reuses token
        assert owner.post(f"{ADM}/bookings/{bid}/tip-request").json()["url"] == d["url"]
        info = requests.get(f"{PUB}/tips/{bid}", params={"t": token}).json()
        assert info["first_name"] == "TEST_" and info["service_name"] == "Residential / Regular Clean"
        assert requests.get(f"{PUB}/tips/{bid}", params={"t": "wrong"}).status_code == 404
        for bad in (0.5, 0, 501):
            assert requests.post(f"{PUB}/tips/{bid}", json={"t": token, "amount": bad, "origin_url": BASE}).status_code == 422
        assert requests.post(f"{PUB}/tips/{bid}", json={"t": "wrong", "amount": 5, "origin_url": BASE}).status_code == 404
        r = requests.post(f"{PUB}/tips/{bid}", json={"t": token, "amount": 12.5, "origin_url": BASE})
        assert r.status_code == 200 and "checkout.stripe.com" in r.json()["checkout_url"]
        tx = DB.payment_transactions.find_one({"booking_id": bid, "kind": "tip"})
        assert tx["amount"] == 12.5
        st = requests.get(f"{BASE}/api/payments/status/{tx['session_id']}").json()
        assert st["kind"] == "tip" and st["payment_status"] != "paid"
        comm = DB.communications.find_one({"lead_id": lead_id, "template": "tip_request"})
        assert comm is not None
