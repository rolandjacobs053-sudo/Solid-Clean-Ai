# Iteration 16: retest of iteration_15 fixes - async roadmap job, SSRF guard, knowledge stats, conflicts(None lead), erase ACTIVE guard, 404s, regression
import os
import time
import uuid

import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
OWNER = {"email": "admin@solidcleanltd.com", "password": "SolidClean#2026"}
DAY = "2026-11-26"
U = uuid.uuid4().hex[:6]
C = f"{BASE_URL}/api/admin/customers"
S = f"{BASE_URL}/api/admin/strategy"
K = f"{BASE_URL}/api/admin/knowledge"


def _db():
    env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
    return MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]


DB = _db()
CID = str(DB.companies.find_one({"slug": "solid-clean"})["_id"])


@pytest.fixture(scope="module")
def owner():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=OWNER)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def st():
    return {"customers": [], "raw_bookings": []}


@pytest.fixture(scope="module", autouse=True)
def cleanup(st):
    yield
    DB.leads.delete_many({"_id": {"$in": [ObjectId(c) for c in st["customers"]]}})
    DB.bookings.delete_many({"lead_id": {"$in": st["customers"]}})
    DB.bookings.delete_many({"_id": {"$in": st["raw_bookings"]}})
    DB.communications.delete_many({"lead_id": {"$in": st["customers"]}})
    DB.goals.delete_many({"title": {"$regex": "^TEST_"}})
    DB.knowledge.delete_many({"source_title": {"$regex": "^TEST_"}})
    DB.knowledge_sources.delete_many({"source_title": {"$regex": "^TEST_"}})


def mk_customer(owner, st, name):
    r = owner.post(C, json={"name": name, "email": f"test_{U}_{len(st['customers'])}@example.com", "address": "1 TEST Street", "postcode": "SW1A 1AA", "contact_method": "phone"})
    assert r.status_code == 200, r.text
    st["customers"].append(r.json()["id"])
    return r.json()["id"]


def bk(slot="08:00", **kw):
    return {"service": "regular", "date": DAY, "slot": slot, "duration_hours": 3, "price": 100, "payment_status": "due", "send_confirmation": False, **kw}


# Async roadmap job: immediate response, dedupe, done with result_id
class TestRoadmapJob:
    def test_async_and_no_duplicate(self, owner):
        before = DB.roadmaps.count_documents({"company_id": CID})
        t0 = time.time()
        r = owner.post(f"{S}/roadmap/generate", timeout=30)
        assert r.status_code == 200 and r.json() == {"status": "running"}, r.text
        assert time.time() - t0 < 10
        r2 = owner.post(f"{S}/roadmap/generate", timeout=30)
        assert r2.json() == {"status": "running"}
        assert owner.get(f"{S}/jobs/roadmap").json()["status"] == "running"
        j = None
        for _ in range(45):
            time.sleep(5)
            j = owner.get(f"{S}/jobs/roadmap").json()
            if j["status"] != "running":
                break
        print("JOB:", j, "elapsed", round(time.time() - t0))
        assert j["status"] == "done", j
        time.sleep(3)
        assert DB.roadmaps.count_documents({"company_id": CID}) == before + 1, "duplicate roadmap generated"
        rm = owner.get(f"{S}/roadmap").json()
        assert rm["id"] == j["result_id"] and len(rm["stages"]) >= 5
        assert "_id" not in j

    def test_job_idle_unknown(self, owner):
        assert owner.get(f"{S}/jobs/nothing_{U}").json() == {"status": "idle"}


# 404s for bad ids
class TestNotFound:
    def test_goal_and_reject(self, owner):
        for gid in ("000000000000000000000000", "bad-id"):
            assert owner.delete(f"{S}/goals/{gid}").status_code == 404
            assert owner.post(f"{S}/approvals/{gid}/reject").status_code == 404


# SSRF guard
class TestSSRF:
    @pytest.mark.parametrize("url", ["http://localhost:8001/api/health", "http://127.0.0.1", "http://169.254.169.254/latest/meta-data", "http://10.0.0.1/"])
    def test_private(self, owner, url):
        r = owner.post(f"{K}/ingest", json={"url": url})
        assert r.status_code == 422 and "private network" in r.json()["detail"], r.text


# Knowledge stats: sources counts title-level, outdated 0
class TestKnowledgeStats:
    def test_paste_counts_one_source(self, owner):
        s0 = owner.get(f"{K}/stats").json()
        assert s0["outdated"] == 0, s0["outdated"]
        txt = ("TEST_ notes. A Surrey cleaning company doubled commercial revenue in two years by targeting dental surgeries and offices with fixed monthly contracts, "
               "audited quality checks and a named supervisor per site. They said client retention reached 95% per year. Cold calling did not work well; "
               "partnerships with local facilities managers and accountants created most introductions. Pricing was based on hours plus a 25% margin target. ") * 2
        r = owner.post(f"{K}/ingest", json={"text": txt, "title": f"TEST_ paste {U}", "source_type": "other"}, timeout=120)
        assert r.status_code == 200, r.text
        print("INGEST:", r.json())
        s1 = owner.get(f"{K}/stats").json()
        print("SOURCES", s0["sources"], "->", s1["sources"], "LESSONS", s0["lessons"], "->", s1["lessons"])
        if r.json()["added"]:
            assert s1["sources"] == s0["sources"] + 1
        assert s1["lessons"] == s0["lessons"] + r.json()["added"]
        for it in [x for x in owner.get(K, params={"q": f"TEST_ paste {U}"}).json() if x["source_title"] == f"TEST_ paste {U}"]:
            assert owner.delete(f"{K}/{it['id']}").status_code == 200
        assert owner.get(f"{K}/stats").json()["sources"] == s0["sources"]


# Customers: conflicts with lead_id None, erase blocked for ACTIVE statuses, regression flow
class TestCustomers:
    def test_none_lead_not_double(self, owner, st):
        base = {"company_id": CID, "lead_id": None, "date": DAY, "duration_hours": 3, "status": "confirmed", "manual": True, "customer": {"name": "TEST_ online"},
                "service_name": "Regular", "total": 100, "payment_status": "paid", "reference": f"TEST-{U}"}
        a = DB.bookings.insert_one({**base, "slot": "14:00"}).inserted_id
        b = DB.bookings.insert_one({**base, "slot": "18:00"}).inserted_id
        st["raw_bookings"] += [a, b]
        r = owner.patch(f"{C}/bookings/{b}", json={"slot": "14:30", "allow_conflict": True})
        assert r.status_code == 200, r.text

    def test_erase_blocked_active(self, owner, st):
        cid = mk_customer(owner, st, f"TEST_ Erase {U}")
        r = owner.post(f"{C}/{cid}/bookings", json=bk("07:00"))
        assert r.status_code == 200, r.text
        bid = ObjectId(r.json()["id"])
        for status in ("awaiting_approval", "pending_payment", "confirmed"):
            DB.bookings.update_one({"_id": bid}, {"$set": {"status": status}})
            assert owner.delete(f"{C}/{cid}").status_code == 409, status
        DB.bookings.update_one({"_id": bid}, {"$set": {"status": "cancelled"}})
        assert owner.delete(f"{C}/{cid}").status_code == 200

    def test_regression_book_reschedule_cancel(self, owner, st):
        cid = mk_customer(owner, st, f"TEST_ Reg {U}")
        r = owner.post(f"{C}/{cid}/bookings", json=bk("06:00"))
        assert r.status_code == 200, r.text
        bid = r.json()["id"]
        r = owner.patch(f"{C}/bookings/{bid}", json={"date": "2026-11-27", "slot": "10:00"})
        assert r.status_code == 200 and r.json()["moved"] is True, r.text
        b = next(x for x in owner.get(f"{C}/{cid}").json()["bookings"] if x["id"] == bid)
        assert b["date"] == "2026-11-27" and b["slot"] == "10:00"
        r = owner.patch(f"{BASE_URL}/api/admin/bookings/{bid}", json={"status": "cancelled"})
        assert r.status_code == 200, r.text
        assert next(x for x in owner.get(f"{C}/{cid}").json()["bookings"] if x["id"] == bid)["status"] == "cancelled"
