# Iteration 15: Customer Management (CRUD, manual bookings, conflicts, edit, cancel, erase), Strategy (goals, insights, reports, approvals, cron), Knowledge base
import os
import time
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
OWNER = {"email": "admin@solidcleanltd.com", "password": "SolidClean#2026"}
STAFF = {"email": "test_iter15_staff@example.com", "password": "TEST_staff#2026", "name": "TEST_ Staff15"}
CRON = os.environ.get("WEBHOOK_CRON_SECRET") or [l.split("=", 1)[1].strip().strip('"') for l in open("/app/backend/.env") if l.startswith("WEBHOOK_CRON_SECRET")][0]
DAY = "2026-11-24"
U = uuid.uuid4().hex[:6]
C = f"{BASE_URL}/api/admin/customers"
S = f"{BASE_URL}/api/admin/strategy"
K = f"{BASE_URL}/api/admin/knowledge"


def login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": creds["email"], "password": creds["password"]})
    assert r.status_code == 200, r.text
    return s


def _db():
    return MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


@pytest.fixture(scope="module")
def owner():
    return login(OWNER)


@pytest.fixture(scope="module")
def st():
    return {"customers": [], "bookings": [], "goals": [], "knowledge": []}


@pytest.fixture(scope="module", autouse=True)
def cleanup(st):
    yield
    d = _db()
    from bson import ObjectId
    d.users.delete_many({"email": STAFF["email"]})
    ids = [ObjectId(c) for c in st["customers"]]
    d.leads.delete_many({"_id": {"$in": ids}})
    d.bookings.delete_many({"lead_id": {"$in": st["customers"]}})
    d.communications.delete_many({"lead_id": {"$in": st["customers"]}})
    d.goals.delete_many({"title": {"$regex": "^TEST_"}})
    d.knowledge.delete_many({"source_title": {"$regex": "^TEST_"}})
    d.knowledge_sources.delete_many({"source_title": {"$regex": "^TEST_"}})


def mk_customer(owner, st, name, email=None, phone=None, postcode="SW1A 1AA"):
    r = owner.post(C, json={"name": name, "phone": phone or "", "email": email or "", "address": "1 TEST Street", "postcode": postcode,
                            "contact_method": "phone", "property_details": "TEST_ 2 bed flat"})
    assert r.status_code == 200, r.text
    st["customers"].append(r.json()["id"])
    return r.json()["id"]


def booking(slot="08:00", price=120, **kw):
    return {"service": "regular", "date": DAY, "slot": slot, "duration_hours": 3, "price": price, "payment_status": "due", "send_confirmation": False, **kw}


# Auth: owner-only areas
class TestAuth:
    PATHS = [("get", "/api/admin/customers"), ("post", "/api/admin/customers"), ("get", "/api/admin/strategy/goals"), ("get", "/api/admin/strategy/insights"),
             ("get", "/api/admin/strategy/reports"), ("get", "/api/admin/strategy/approvals"), ("get", "/api/admin/knowledge"), ("get", "/api/admin/knowledge/stats")]

    def test_401(self):
        bad = [(p, r.status_code) for m, p in self.PATHS if (r := getattr(requests, m)(f"{BASE_URL}{p}", json={})).status_code != 401]
        assert not bad, bad

    def test_403_staff(self, owner):
        r = owner.post(f"{BASE_URL}/api/admin/staff", json={"name": STAFF["name"], "email": STAFF["email"], "password": STAFF["password"]})
        assert r.status_code in (200, 409), r.text
        s = login(STAFF)
        bad = [(p, r.status_code) for m, p in self.PATHS if (r := getattr(s, m)(f"{BASE_URL}{p}", json={})).status_code != 403]
        assert not bad, bad


# Customers CRUD + search + duplicates
class TestCustomers:
    def test_create_get_search_dup(self, owner, st):
        cid = mk_customer(owner, st, f"TEST_ Alice {U}", f"test_alice_{U}@example.com", f"07111 {U[:3]} 999".replace("a", "1").replace("b", "2").replace("c", "3").replace("d", "4").replace("e", "5").replace("f", "6"), "KT1 2AB")
        g = owner.get(f"{C}/{cid}").json()
        c = g["customer"]
        assert c["name"] == f"TEST_ Alice {U}" and c["postcode"] == "KT1 2AB" and " " not in c["phone"] and "_id" not in c
        assert g["timeline"] and g["bookings"] == []
        phone = c["phone"]
        for q in (f"Alice {U}", f"test_alice_{U}", "KT1 2AB", phone, phone[-6:]):
            ids = [x["id"] for x in owner.get(C, params={"q": q}).json()]
            assert cid in ids, f"search {q} failed"
        # spaced phone search
        spaced = phone[:5] + " " + phone[5:]
        assert cid in [x["id"] for x in owner.get(C, params={"q": spaced}).json()], "spaced phone search"
        r = owner.post(C, json={"name": "TEST_ Dup", "email": f"TEST_alice_{U}@example.com"})
        assert r.status_code == 409 and r.json()["detail"]["existing_id"] == cid
        r = owner.post(C, json={"name": "TEST_ Dup", "phone": phone})
        assert r.status_code == 409
        assert owner.post(C, json={"name": "TEST_ None"}).status_code == 422
        assert owner.post(C, json={"name": "TEST_ Bad", "email": "bad"}).status_code == 422
        st["alice"] = cid

    def test_update(self, owner, st):
        cid = st["alice"]
        r = owner.put(f"{C}/{cid}", json={"name": f"TEST_ Alice {U} Edited", "email": f"test_alice_{U}@example.com", "postcode": "kt1 9zz", "notes": "TEST_ note"})
        assert r.status_code == 200
        c = owner.get(f"{C}/{cid}").json()["customer"]
        assert c["name"].endswith("Edited") and c["postcode"] == "KT1 9ZZ" and c["notes"] == "TEST_ note"

    def test_404(self, owner):
        assert owner.get(f"{C}/000000000000000000000000").status_code == 404


# Bookings: create, conflicts, edit, cancel, erase
class TestBookings:
    def test_create_and_central(self, owner, st):
        cid = st["alice"]
        r = owner.post(f"{C}/{cid}/bookings", json=booking("08:00", 150, requirements="TEST_ req"))
        assert r.status_code == 200, r.text
        bid = r.json()["id"]
        st["b1"] = bid
        g = owner.get(f"{C}/{cid}").json()
        b = next(x for x in g["bookings"] if x["id"] == bid)
        assert b["status"] == "confirmed" and b["manual"] and b["total"] == 150 and b["balance_due"] == 150
        assert not [m for m in g["communications"]], "no comms when send_confirmation false"
        lst = owner.get(f"{BASE_URL}/api/admin/bookings").json()
        items = lst if isinstance(lst, list) else lst.get("items") or lst.get("bookings") or []
        assert bid in [x["id"] for x in items], "manual booking missing from /api/admin/bookings"

    def test_unknown_service(self, owner, st):
        assert owner.post(f"{C}/{st['alice']}/bookings", json={**booking("14:00"), "service": "nope"}).status_code == 400

    def test_same_customer_double_booking(self, owner, st):
        r = owner.post(f"{C}/{st['alice']}/bookings", json=booking("09:00", allow_conflict=True))
        assert r.status_code == 409
        d = r.json()["detail"]
        assert "Double booking" in d["message"] and not d.get("can_override")

    def test_capacity_override(self, owner, st):
        bob = mk_customer(owner, st, f"TEST_ Bob {U}", f"test_bob_{U}@example.com")
        carl = mk_customer(owner, st, f"TEST_ Carl {U}", f"test_carl_{U}@example.com")
        r = owner.post(f"{C}/{bob}/bookings", json=booking("08:00"))
        assert r.status_code == 200, r.text  # 1 overlapping < capacity 2
        st["b_bob"] = r.json()["id"]
        chk = owner.post(f"{C}/{carl}/conflicts", json=booking("09:00")).json()
        assert chk["over_capacity"] and not chk["double_booking"] and len(chk["conflicts"]) == 2
        r = owner.post(f"{C}/{carl}/bookings", json=booking("09:00"))
        assert r.status_code == 409 and r.json()["detail"]["can_override"] is True
        r = owner.post(f"{C}/{carl}/bookings", json=booking("09:00", allow_conflict=True))
        assert r.status_code == 200
        st["carl"], st["b_carl"] = carl, r.json()["id"]

    def test_edit_payment_and_move(self, owner, st):
        bid = st["b1"]
        r = owner.patch(f"{C}/bookings/{bid}", json={"price": 200, "payment_status": "deposit_paid", "amount_paid": 50})
        assert r.status_code == 200, r.text
        g = owner.get(f"{C}/{st['alice']}").json()
        b = next(x for x in g["bookings"] if x["id"] == bid)
        assert b["total"] == 200 and b["deposit_amount"] == 50 and b["balance_due"] == 150
        assert any("updated" in t["text"] for t in g["timeline"])
        # move into a full slot (bob + carl at 08/09) -> capacity conflict only (alice excluded)
        r = owner.patch(f"{C}/bookings/{st['b_bob']}", json={"slot": "14:00"})
        assert r.status_code == 200 and r.json()["moved"]
        r = owner.patch(f"{C}/bookings/{bid}", json={"slot": "14:00", "date": DAY})
        assert r.status_code == 200  # only bob at 14:00 -> 1 < 2
        r = owner.patch(f"{C}/bookings/{st['b_carl']}", json={"slot": "15:00"})
        assert r.status_code == 409 and r.json()["detail"].get("can_override")
        r = owner.patch(f"{C}/bookings/{st['b_carl']}", json={"slot": "15:00", "allow_conflict": True})
        assert r.status_code == 200
        # only-payment edit to paid
        r = owner.patch(f"{C}/bookings/{bid}", json={"payment_status": "paid"})
        b = next(x for x in owner.get(f"{C}/{st['alice']}").json()["bookings"] if x["id"] == bid)
        assert b["balance_due"] == 0 and b["deposit_amount"] == 200

    def test_same_customer_move_conflict(self, owner, st):
        r = owner.post(f"{C}/{st['alice']}/bookings", json=booking("08:00", 90, date="2026-11-25"))
        assert r.status_code == 200
        b2 = r.json()["id"]
        st["b2"] = b2
        r = owner.patch(f"{C}/bookings/{b2}", json={"date": DAY, "slot": "15:00", "allow_conflict": True})
        assert r.status_code == 409 and "Double booking" in r.json()["detail"]["message"]

    def test_online_booking_price_locked(self, owner):
        d = _db()
        b = d.bookings.find_one({"manual": {"$ne": True}, "status": "confirmed"})
        if not b:
            pytest.skip("no online booking")
        r = owner.patch(f"{C}/bookings/{b['_id']}", json={"price": 1})
        assert r.status_code == 409

    def test_erase_blocked_then_cancel_then_erase(self, owner, st):
        cid = st["alice"]
        assert owner.delete(f"{C}/{cid}").status_code == 409
        for bid in (st["b1"], st["b2"]):
            r = owner.patch(f"{BASE_URL}/api/admin/bookings/{bid}", json={"status": "cancelled"})
            assert r.status_code == 200, r.text
        g = owner.get(f"{C}/{cid}").json()
        assert all(x["status"] == "cancelled" for x in g["bookings"])
        assert owner.patch(f"{C}/bookings/{st['b1']}", json={"slot": "11:00"}).status_code == 409
        staff = login(STAFF)
        assert staff.delete(f"{C}/{cid}").status_code == 403
        assert owner.delete(f"{C}/{cid}").status_code == 200
        assert owner.get(f"{C}/{cid}").status_code == 404
        assert cid not in [x["id"] for x in owner.get(C).json()]
        lead = _db().leads.find_one({"_id": __import__("bson").ObjectId(cid)})
        assert lead["email"] is None and lead["name"] == "Erased customer"


# Strategy: goals, insights, reports, cron
class TestStrategy:
    def test_goals(self, owner):
        g = owner.get(f"{S}/goals").json()
        titles = [x["title"] for x in g["goals"]]
        assert any("10,000" in t for t in titles) and any("400" in t for t in titles)
        assert all("progress_pct" in x and "current" in x for x in g["goals"])
        r = owner.post(f"{S}/goals", json={"title": "TEST_ goal", "metric": "monthly_jobs", "target": 50})
        gid = r.json()["id"]
        assert any(x["id"] == gid for x in owner.get(f"{S}/goals").json()["goals"])
        assert owner.post(f"{S}/goals", json={"title": "TEST_ bad", "metric": "x", "target": 5}).status_code == 400
        owner.delete(f"{S}/goals/{gid}")
        assert not any(x["id"] == gid for x in owner.get(f"{S}/goals").json()["goals"])

    def test_insights(self, owner):
        r = owner.get(f"{S}/insights")
        assert r.status_code == 200
        print("INSIGHTS:", str(r.json())[:600])

    def test_cron(self, owner):
        url = f"{BASE_URL}/api/cron/manager-report/daily"
        assert requests.post(url).status_code == 401
        assert requests.post(url, headers={"Authorization": "Bearer wrong"}).status_code == 401
        before = len(owner.get(f"{S}/reports").json())
        wid = f"TEST_{U}"
        r = requests.post(url, headers={"Authorization": f"Bearer {CRON}", "x-webhook-id": wid})
        assert r.status_code == 200 and not r.json().get("duplicate")
        r = requests.post(url, headers={"Authorization": f"Bearer {CRON}", "x-webhook-id": wid})
        assert r.json().get("duplicate") is True
        for _ in range(24):
            time.sleep(5)
            if len(owner.get(f"{S}/reports").json()) > before:
                break
        assert len(owner.get(f"{S}/reports").json()) > before, "cron report not created"
        assert requests.post(f"{BASE_URL}/api/cron/manager-report/yearly", headers={"Authorization": f"Bearer {CRON}"}).status_code == 422

    def test_approvals_scan_list(self, owner):
        r = owner.post(f"{S}/approvals/scan", timeout=120)
        assert r.status_code == 200, r.text
        print("SCAN:", r.json())
        assert isinstance(owner.get(f"{S}/approvals").json(), list)
        assert owner.post(f"{S}/approvals/000000000000000000000000/approve").status_code == 404


# Knowledge base
class TestKnowledge:
    def test_stats_list_search(self, owner):
        s = owner.get(f"{K}/stats").json()
        print("STATS:", s["lessons"], s["sources"])
        assert s["lessons"] >= 100 and s["sources"] >= 15
        assert len(owner.get(K, params={"q": "franchis"}).json()) > 0
        t = owner.get(K, params={"topic": "commercial_contracts"}).json()
        assert t and all(x["topic"] == "commercial_contracts" for x in t)

    def test_blocked_and_short(self, owner):
        r = owner.post(f"{K}/ingest", json={"url": "https://www.tiktok.com/@x/video/1"})
        assert r.status_code == 422 and "TikTok" in r.json()["detail"]
        r = owner.post(f"{K}/ingest", json={"url": "https://instagram.com/p/abc"})
        assert r.status_code == 422
        assert owner.post(f"{K}/ingest", json={"text": "short"}).status_code == 422

    def test_ingest_text_dup_patch_delete(self, owner, st):
        txt = ("TEST_ notes. A London cleaning firm grew recurring revenue from 20 to 120 weekly clients in 18 months by offering a fixed same-cleaner guarantee, "
               "a 10% discount for direct debit and sending a quarterly satisfaction survey. They said churn fell from 8% to 3% per month. They tried Facebook ads, "
               "which did not work for them because cost per lead was too high. Referral cards given after each clean generated about a third of new customers. ") * 2
        url = f"https://example.com/TEST_{U}"
        r = owner.post(f"{K}/ingest", json={"url": url, "text": txt, "title": "TEST_ notes", "source_type": "other"}, timeout=120)
        assert r.status_code == 200, r.text
        assert r.json()["added"] >= 1
        items = [x for x in owner.get(K, params={"q": "TEST_ notes"}).json() if x["source_title"] == "TEST_ notes"]
        assert items
        assert owner.post(f"{K}/ingest", json={"url": url, "text": txt, "title": "TEST_ notes"}).status_code == 409
        kid = items[0]["id"]
        assert owner.patch(f"{K}/{kid}", json={"status": "outdated"}).json()["status"] == "outdated"
        assert owner.patch(f"{K}/{kid}", json={"status": "active"}).json()["status"] == "active"
        assert owner.delete(f"{K}/{kid}").status_code == 200
        assert owner.delete(f"{K}/{kid}").status_code == 404
