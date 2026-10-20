"""Iteration 9: carpet cleaning quote-request -> owner quote -> accept & pay -> owner approval flow,
carpet 422 on main booking endpoint, decline-after-paid refund. Creates TEST_ data and cleans it up."""
import datetime as dt
import io
import os
import uuid

import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from PIL import Image
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
PUB = f"{BASE}/api/public/solid-clean"
CQ = f"{PUB}/carpet-quotes"
ADM = f"{BASE}/api/admin/carpet-quotes"
OWNER = {"email": "admin@solidcleanltd.com", "password": "SolidClean#2026"}
ENV = dotenv_values("/app/backend/.env")
DB = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
EMAILS = []


def _day(n):
    return (dt.date.today() + dt.timedelta(days=n)).isoformat()


def _email():
    e = f"test_carpet_{uuid.uuid4().hex[:8]}@example.com"
    EMAILS.append(e)
    return e


def _payload(**kw):
    p = {"areas": {"living_room": 1, "stairs": 1}, "stairs_steps": 14, "stairs_landing": "yes",
         "answers": {"visible_stains": "yes", "heavily_soiled": "no", "pets": "yes", "pet_hair": "yes", "stain_treatment": "yes"},
         "notes": "TEST_ notes", "photos": [], "preferred_date": _day(10), "preferred_time": "10:00",
         "contact": {"name": "TEST_ Carpet Customer", "phone": "07700900123", "email": _email()},
         "postcode": "sw1a 1aa", "address": "TEST_ 10 Downing Street, London"}
    p.update(kw)
    return p


@pytest.fixture(scope="module")
def owner():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=OWNER, timeout=20)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    qs = list(DB.carpet_quotes.find({"contact.email": {"$in": EMAILS}}))
    qids = [str(q["_id"]) for q in qs]
    bids = [str(b["_id"]) for b in DB.bookings.find({"carpet_quote_id": {"$in": qids}})]
    DB.payment_transactions.delete_many({"booking_id": {"$in": bids}})
    DB.bookings.delete_many({"carpet_quote_id": {"$in": qids}})
    DB.photos.delete_many({"carpet_quote_id": {"$in": qids}})
    lids = [q["lead_id"] for q in qs]
    DB.communications.delete_many({"$or": [{"to": {"$in": EMAILS}}, {"lead_id": {"$in": lids}}]})
    DB.leads.delete_many({"email": {"$in": EMAILS}})
    DB.carpet_quotes.delete_many({"_id": {"$in": [q["_id"] for q in qs]}})


def _photo():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (120, 30, 30)).save(buf, "JPEG")
    r = requests.post(f"{PUB}/photos", files={"file": ("t.jpg", buf.getvalue(), "image/jpeg")}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    return {"id": d["id"], "token": d["token"]}


# --- validation
@pytest.mark.parametrize("bad", [
    {"areas": {"kitchen": 1}},
    {"areas": {"stairs": 1}, "stairs_steps": 0},
    {"preferred_date": _day(-1)},
    {"preferred_date": _day(0)},
    {"answers": {"parking": "yes"}},
    {"areas": {"bedroom": 0}},
])
def test_request_validation(bad):
    r = requests.post(CQ, json=_payload(**bad), timeout=20)
    assert r.status_code == 422, r.text


def test_main_booking_rejects_carpet():
    cfg = requests.get(f"{PUB}/config", timeout=15).json()
    svc = [s for s in cfg["pricing"]["services"] if s.get("key") == "carpet"]
    assert svc and svc[0].get("from_price") == 100 and svc[0].get("requires_survey") is True
    body = {"quote": {"service": "carpet", "property_type": "flat", "bedrooms": 2, "bathrooms": 1, "living_rooms": 1, "condition": "good",
                      "extras": [], "postcode": "SW1A 1AA", "address": "TEST_ 8 Carpet Street, London", "furnished": "furnished", "flooring": "carpet", "pets": "no"},
            "contact": {"name": "TEST_ carpetbk", "email": _email(), "phone": "07700900111"},
            "date": _day(10), "slot": "10:00", "access": {"method": "customer_present"},
            "accepted_policies": {p["key"]: p["published_version"] for p in cfg["policies"] if p.get("require_acceptance")},
            "pay_terms_accepted": True, "tip": 0, "origin_url": BASE, "source": "website", "photos": []}
    r = requests.post(f"{PUB}/bookings", json=body, timeout=20)
    assert r.status_code == 422, r.text
    assert "carpet cleaning quote form" in r.json()["detail"]


# --- full flow
class TestCarpetFlow:
    st = {}

    def test_1_request(self):
        before = DB.bookings.count_documents({})
        p = _payload(photos=[_photo(), _photo()])
        r = requests.post(CQ, json=p, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["message"].startswith("Thank you for your carpet cleaning enquiry. Your request has been received and is awaiting review.")
        assert d["message"].endswith("Your booking is not confirmed until we approve the appointment and confirm the details with you.")
        q = DB.carpet_quotes.find_one({"_id": ObjectId(d["id"])})
        assert q["status"] == "awaiting_review" and q["postcode"] == "SW1A 1AA" and q["stairs_steps"] == 14
        assert DB.bookings.count_documents({}) == before
        assert DB.photos.count_documents({"carpet_quote_id": d["id"], "status": "attached"}) == 2
        email = p["contact"]["email"]
        assert DB.communications.find_one({"to": email, "template": "carpet_quote_ack"}) or DB.communications.find_one({"lead_id": q["lead_id"], "template": "carpet_quote_ack"})
        assert not DB.communications.find_one({"lead_id": q["lead_id"], "template": "booking_confirmation"})
        self.st.update(id=d["id"], email=email, lead=q["lead_id"])

    def test_2_admin_list_detail(self, owner):
        r = owner.get(ADM, timeout=20)
        assert r.status_code == 200
        row = [x for x in r.json() if x["id"] == self.st["id"]]
        assert row and "token" not in row[0]
        r = owner.get(f"{ADM}/{self.st['id']}", timeout=20)
        assert r.status_code == 200 and len(r.json()["photos"]) == 2
        assert requests.get(ADM, timeout=20).status_code == 401

    def test_3_view_before_quote_404(self):
        assert requests.get(f"{CQ}/{self.st['id']}", params={"t": "x"}, timeout=20).status_code == 404

    def test_4_send_quote(self, owner):
        assert owner.post(f"{ADM}/{self.st['id']}/quote", json={"price": 150, "date": _day(-1), "time": "10:00"}, timeout=20).status_code == 422
        r = owner.post(f"{ADM}/{self.st['id']}/quote", json={"price": 150, "date": _day(12), "time": "10:00", "message": "TEST_ msg"}, timeout=30)
        assert r.status_code == 200, r.text
        url = r.json()["url"]
        assert f"/carpet-cleaning/quote/{self.st['id']}?t=" in url and url.startswith("https://")
        q = DB.carpet_quotes.find_one({"_id": ObjectId(self.st["id"])})
        assert q["status"] == "quoted" and q["token"] in url
        self.st["t"] = q["token"]

    def test_5_view_and_accept(self):
        assert requests.get(f"{CQ}/{self.st['id']}", params={"t": "wrong"}, timeout=20).status_code == 404
        r = requests.get(f"{CQ}/{self.st['id']}", params={"t": self.st["t"]}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["price"] == 150 and d["status"] == "quoted" and d["stairs_steps"] == 14 and d["first_name"] == "TEST_"
        r = requests.post(f"{CQ}/{self.st['id']}/accept", json={"t": self.st["t"], "origin_url": BASE}, timeout=20)
        assert r.status_code == 409
        r = requests.post(f"{CQ}/{self.st['id']}/accept", json={"t": self.st["t"], "pay_terms_accepted": True, "origin_url": BASE}, timeout=40)
        assert r.status_code == 200, r.text
        assert "checkout.stripe.com" in r.json()["checkout_url"]
        b = DB.bookings.find_one({"carpet_quote_id": self.st["id"], "status": "pending_payment"})
        assert b and b["service"] == "carpet" and b["total"] == 150 and b["balance_due"] == 0
        self.st.update(bid=str(b["_id"]), sid=b["session_id"])

    def test_6_approve_before_paid_400(self, owner):
        assert owner.post(f"{ADM}/{self.st['id']}/approve", timeout=20).status_code == 400

    def test_7_simulate_paid(self):
        DB.payment_transactions.update_one({"session_id": self.st["sid"]}, {"$set": {"payment_status": "paid", "status": "completed"}})
        r = requests.get(f"{BASE}/api/payments/status/{self.st['sid']}", timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["kind"] == "carpet"
        b = DB.bookings.find_one({"_id": ObjectId(self.st["bid"])})
        assert b["status"] == "awaiting_approval" and b["payment_status"] == "paid"
        q = DB.carpet_quotes.find_one({"_id": ObjectId(self.st["id"])})
        assert q["status"] == "accepted" and q["booking_id"] == self.st["bid"]
        assert DB.communications.count_documents({"lead_id": self.st["lead"], "template": "carpet_payment_received"}) == 1
        # idempotent
        requests.get(f"{BASE}/api/payments/status/{self.st['sid']}", timeout=30)
        assert DB.communications.count_documents({"lead_id": self.st["lead"], "template": "carpet_payment_received"}) == 1
        assert not DB.communications.find_one({"lead_id": self.st["lead"], "template": "booking_confirmation"})
        v = requests.get(f"{CQ}/{self.st['id']}", params={"t": self.st["t"]}, timeout=20).json()
        assert v["status"] == "accepted"
        r = requests.post(f"{CQ}/{self.st['id']}/accept", json={"t": self.st["t"], "pay_terms_accepted": True, "origin_url": BASE}, timeout=20)
        assert r.status_code == 409

    def test_8_approve(self, owner):
        r = owner.post(f"{ADM}/{self.st['id']}/approve", timeout=30)
        assert r.status_code == 200, r.text
        assert DB.bookings.find_one({"_id": ObjectId(self.st["bid"])})["status"] == "confirmed"
        assert DB.carpet_quotes.find_one({"_id": ObjectId(self.st["id"])})["status"] == "confirmed"
        assert DB.communications.find_one({"lead_id": self.st["lead"], "template": "booking_confirmation"})
        assert owner.post(f"{ADM}/{self.st['id']}/decline", json={}, timeout=20).status_code == 400


class TestDeclinePaid:
    def test_decline_after_paid_refund(self, owner):
        r = requests.post(CQ, json=_payload(areas={"bedroom": 2}, stairs_steps=0), timeout=30)
        assert r.status_code == 200, r.text
        qid = r.json()["id"]
        assert owner.post(f"{ADM}/{qid}/quote", json={"price": 120, "date": _day(15), "time": "12:00"}, timeout=30).status_code == 200
        t = DB.carpet_quotes.find_one({"_id": ObjectId(qid)})["token"]
        assert requests.post(f"{CQ}/{qid}/accept", json={"t": t, "pay_terms_accepted": True, "origin_url": BASE}, timeout=40).status_code == 200
        b = DB.bookings.find_one({"carpet_quote_id": qid, "status": "pending_payment"})
        DB.payment_transactions.update_one({"session_id": b["session_id"]}, {"$set": {"payment_status": "paid", "status": "completed"}})
        requests.get(f"{BASE}/api/payments/status/{b['session_id']}", timeout=30)
        r = owner.post(f"{ADM}/{qid}/decline", json={"message": "TEST_ sorry"}, timeout=30)
        assert r.status_code == 200, r.text
        b = DB.bookings.find_one({"_id": b["_id"]})
        assert b["status"] == "cancelled" and b["payment_status"] == "refund_due" and b["refund"]["amount"] == 120
        assert DB.carpet_quotes.find_one({"_id": ObjectId(qid)})["status"] == "declined"
        assert requests.get(f"{CQ}/{qid}", params={"t": t}, timeout=20).status_code == 404


def test_rate_limit_per_email():
    e = _email()
    codes = []
    for _ in range(4):
        p = _payload(areas={"hallway": 1}, stairs_steps=0)
        p["contact"]["email"] = e
        codes.append(requests.post(CQ, json=p, timeout=30).status_code)
    assert codes == [200, 200, 200, 429], codes


def test_decline_while_checkout_open_then_paid():
    """Owner declines a quoted request while the customer's Stripe checkout is still open; a late payment must not revive it."""
    r = requests.post(CQ, json=_payload(areas={"office": 1}, stairs_steps=0), timeout=30)
    qid = r.json()["id"]
    s = requests.Session()
    s.post(f"{BASE}/api/auth/login", json=OWNER, timeout=20)
    s.post(f"{ADM}/{qid}/quote", json={"price": 110, "date": _day(15), "time": "12:00"}, timeout=30)
    t = DB.carpet_quotes.find_one({"_id": ObjectId(qid)})["token"]
    requests.post(f"{CQ}/{qid}/accept", json={"t": t, "pay_terms_accepted": True, "origin_url": BASE}, timeout=40)
    b = DB.bookings.find_one({"carpet_quote_id": qid, "status": "pending_payment"})
    assert s.post(f"{ADM}/{qid}/decline", json={}, timeout=30).status_code == 200
    DB.payment_transactions.update_one({"session_id": b["session_id"]}, {"$set": {"payment_status": "paid", "status": "completed"}})
    requests.get(f"{BASE}/api/payments/status/{b['session_id']}", timeout=30)
    q = DB.carpet_quotes.find_one({"_id": ObjectId(qid)})
    b2 = DB.bookings.find_one({"_id": b["_id"]})
    assert q["status"] == "declined", f"declined quote revived to {q['status']} (booking {b2['status']}/{b2['payment_status']})"
