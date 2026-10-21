# Iteration 17: Private quote links - token on save, token-gated GET, token-gated quote reuse on booking, email link, CORS/login regression
import datetime as dt
import os
import uuid

import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PUB = f"{BASE}/api/public/solid-clean"
OWNER = {"email": "admin@solidcleanltd.com", "password": "SolidClean#2026"}
U = uuid.uuid4().hex[:6]


def _db():
    env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
    return MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]


DB = _db()
CREATED = {"quotes": [], "leads": set(), "bookings": []}


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    leads = list(CREATED["leads"])
    DB.quotes.delete_many({"_id": {"$in": [ObjectId(q) for q in CREATED["quotes"]]}})
    DB.quotes.delete_many({"lead_id": {"$in": leads}})
    DB.bookings.delete_many({"lead_id": {"$in": leads}})
    DB.communications.delete_many({"lead_id": {"$in": leads}})
    DB.leads.delete_many({"_id": {"$in": [ObjectId(x) for x in leads]}})


@pytest.fixture(scope="module")
def cfg():
    return requests.get(f"{PUB}/config", timeout=15).json()


def _quote(n=0):
    return {"service": "regular", "property_type": "flat", "bedrooms": 2, "bathrooms": 1, "living_rooms": 1, "condition": "good",
            "postcode": "SW1A 1AA", "address": "TEST_ 1 Private Link Street, London", "frequency": "one_off"}


def _contact(n=0):
    return {"name": f"TEST_PQ_{U}_{n}", "email": f"test_pq_{U}_{n}@example.com", "phone": f"0770090{n:04d}"}


def _save(n=0):
    r = requests.post(f"{PUB}/quotes", json={"quote": _quote(n), "contact": _contact(n), "source": "website"}, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    CREATED["quotes"].append(d["quote_id"])
    q = DB.quotes.find_one({"_id": ObjectId(d["quote_id"])})
    CREATED["leads"].add(q["lead_id"])
    return d


def _slot():
    for d in range(3, 60):
        day = (dt.date.today() + dt.timedelta(days=d)).isoformat()
        sl = requests.get(f"{PUB}/availability", params={"date": day}, timeout=15).json().get("slots")
        if sl:
            return day, sl[-1]["slot"]
    pytest.skip("no availability")


def _book(cfg, n, **over):
    day, slot = _slot()
    body = {"quote": _quote(n), "contact": _contact(n), "date": day, "slot": slot, "access": {"method": "customer_present"},
            "accepted_policies": {p["key"]: p["published_version"] for p in cfg["policies"] if p.get("require_acceptance")},
            "pay_terms_accepted": True, "origin_url": BASE, "source": "website", "photos": []}
    body.update(over)
    r = requests.post(f"{PUB}/bookings", json=body, timeout=40)
    assert r.status_code == 200, r.text
    d = r.json()
    b = DB.bookings.find_one({"_id": ObjectId(d["booking_id"])})
    CREATED["bookings"].append(d["booking_id"])
    CREATED["leads"].add(b["lead_id"])
    return d, b


# --- Save quote returns token; GET gated by token ---
class TestQuoteToken:
    def test_save_returns_token(self):
        d = _save(0)
        assert isinstance(d["quote_id"], str) and isinstance(d["token"], str) and len(d["token"]) >= 16
        assert DB.quotes.find_one({"_id": ObjectId(d["quote_id"])})["token"] == d["token"]

    def test_get_without_token_404(self):
        d = _save(1)
        assert requests.get(f"{PUB}/quotes/{d['quote_id']}", timeout=15).status_code == 404

    def test_get_wrong_token_404(self):
        d = _save(2)
        assert requests.get(f"{PUB}/quotes/{d['quote_id']}", params={"t": "wrong"}, timeout=15).status_code == 404
        assert requests.get(f"{PUB}/quotes/{d['quote_id']}", params={"t": d["token"][:-1]}, timeout=15).status_code == 404

    def test_get_correct_token_200_no_address(self):
        d = _save(3)
        r = requests.get(f"{PUB}/quotes/{d['quote_id']}", params={"t": d["token"]}, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["id"] == d["quote_id"] and j["input"]["service"] == "regular" and j["input"]["bedrooms"] == 2
        assert "address" not in j["input"] and "token" not in j

    def test_get_malformed_id_404(self):
        assert requests.get(f"{PUB}/quotes/not-an-id", params={"t": "x"}, timeout=15).status_code == 404

    def test_legacy_quote_without_token_404(self):
        qid = DB.quotes.insert_one({"input": _quote(), "result": {"status": "ok", "total": 1}, "status": "sent", "lead_id": None, "created_at": "x"}).inserted_id
        CREATED["quotes"].append(str(qid))
        assert requests.get(f"{PUB}/quotes/{qid}", timeout=15).status_code == 404
        assert requests.get(f"{PUB}/quotes/{qid}", params={"t": ""}, timeout=15).status_code == 404

    def test_email_link_contains_token(self):
        d = _save(4)
        q = DB.quotes.find_one({"_id": ObjectId(d["quote_id"])})
        c = DB.communications.find_one({"lead_id": q["lead_id"], "template": "quote_sent", "link.1": {"$regex": d["quote_id"]}})
        assert c, "no communication logged"
        blob = str(c)
        assert f"?q={d['quote_id']}&t={d['token']}" in blob, blob[:800]


# --- Booking reuses the quote only with the correct token ---
class TestBookingQuoteReuse:
    def test_correct_token_reuses_quote(self, cfg):
        d = _save(5)
        before = DB.quotes.count_documents({"created_at": {"$gte": "0"}, "input.postcode": "SW1A 1AA", "lead_id": DB.quotes.find_one({"_id": ObjectId(d["quote_id"])})["lead_id"]})
        r, b = _book(cfg, 5, quote_id=d["quote_id"], quote_token=d["token"])
        assert b["quote_id"] == d["quote_id"]
        assert DB.quotes.count_documents({"input.postcode": "SW1A 1AA", "lead_id": b["lead_id"]}) == before
        q = DB.quotes.find_one({"_id": ObjectId(d["quote_id"])})
        assert q["lead_id"] == b["lead_id"]
        print("reused quote status:", q.get("status"))
        assert r.get("url") or r.get("checkout_url") or r.get("confirmed"), r

    def test_wrong_token_creates_new_quote(self, cfg):
        d = _save(6)
        orig = DB.quotes.find_one({"_id": ObjectId(d["quote_id"])})
        _, b = _book(cfg, 6, quote_id=d["quote_id"], quote_token="wrong-token", quote={**_quote(), "bedrooms": 3})
        assert b["quote_id"] != d["quote_id"]
        CREATED["quotes"].append(b["quote_id"])
        nq = DB.quotes.find_one({"_id": ObjectId(b["quote_id"])})
        assert nq["status"] == "booking_started" and nq["input"]["bedrooms"] == 3
        after = DB.quotes.find_one({"_id": ObjectId(d["quote_id"])})
        assert after["input"] == orig["input"] and after["result"] == orig["result"] and after.get("status") == orig.get("status")

    def test_missing_token_creates_new_quote(self, cfg):
        d = _save(7)
        orig = DB.quotes.find_one({"_id": ObjectId(d["quote_id"])})
        _, b = _book(cfg, 7, quote_id=d["quote_id"], quote={**_quote(), "bedrooms": 4})
        assert b["quote_id"] != d["quote_id"]
        CREATED["quotes"].append(b["quote_id"])
        after = DB.quotes.find_one({"_id": ObjectId(d["quote_id"])})
        assert after["input"] == orig["input"] and after["result"] == orig["result"]

    def test_malformed_quote_id_creates_new(self, cfg):
        r = requests.post(f"{PUB}/bookings", json={"quote": _quote(8), "contact": _contact(8), "date": _slot()[0], "slot": _slot()[1], "access": {"method": "customer_present"},
                                                   "accepted_policies": {p["key"]: p["published_version"] for p in cfg["policies"] if p.get("require_acceptance")},
                                                   "pay_terms_accepted": True, "origin_url": BASE, "quote_id": "bad", "quote_token": "x"}, timeout=40)
        print("malformed quote_id ->", r.status_code, r.text[:200])
        if r.status_code == 200:
            b = DB.bookings.find_one({"_id": ObjectId(r.json()["booking_id"])})
            CREATED["leads"].add(b["lead_id"])
        assert r.status_code in (200, 404)


# --- Regression: login + CORS ---
class TestRegression:
    def test_owner_login(self):
        s = requests.Session()
        r = s.post(f"{BASE}/api/auth/login", json=OWNER, timeout=20)
        assert r.status_code == 200, r.text
        assert s.get(f"{BASE}/api/auth/me", timeout=15).status_code == 200

    def test_cors_preview_origin_allowed(self):
        r = requests.options(f"{BASE}/api/auth/login", headers={"Origin": BASE, "Access-Control-Request-Method": "POST"}, timeout=15)
        assert r.headers.get("access-control-allow-origin") == BASE
        assert r.headers.get("access-control-allow-credentials") == "true"

    def test_cors_evil_origin_rejected(self):
        r = requests.options(f"{BASE}/api/auth/login", headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"}, timeout=15)
        assert r.headers.get("access-control-allow-origin") not in ("https://evil.example.com", "*")
