"""Iteration 5: full upfront payment, N/E/W/EC postcodes, commercial walkthroughs (public + admin owner-only),
before/after job photos on bookings. Uses delivered@resend.dev; TEST_ prefix; cleans up via mongo on teardown."""
import datetime as dt
import io
import os
import uuid

import pytest
import requests
from bson import ObjectId
from PIL import Image
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
SLUG = "solid-clean"
PUB = f"{BASE}/api/public/{SLUG}"
OWNER = {"email": "admin@solidcleanltd.com", "password": "SolidClean#2026"}
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
CREATED = {"bookings": [], "walkthroughs": [], "photos": [], "staff": []}


def _img(color=(10, 120, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buf, "JPEG")
    return buf.getvalue()


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def owner():
    return _login(OWNER)


@pytest.fixture(scope="module")
def cfg():
    return requests.get(f"{PUB}/config", timeout=15).json()


def _slot():
    for d in range(2, 60):
        day = (dt.date.today() + dt.timedelta(days=d)).isoformat()
        sl = requests.get(f"{PUB}/availability", params={"date": day}, timeout=15).json().get("slots")
        if sl:
            return day, sl[0]["slot"]
    pytest.skip("no availability")


def _booking_body(cfg, postcode="SW1A 1AA"):
    day, slot = _slot()
    return {"quote": {"service": "regular", "property_type": "flat", "bedrooms": 2, "bathrooms": 1, "living_rooms": 1,
                      "condition": "good", "extras": [], "postcode": postcode, "address": "TEST_ 5 Iter Street, London",
                      "furnished": "furnished", "flooring": "carpet", "pets": "no"},
            "contact": {"name": f"TEST_iter5_{uuid.uuid4().hex[:5]}", "email": "delivered@resend.dev", "phone": "07700900111"},
            "date": day, "slot": slot, "access": {"method": "customer_present"},
            "accepted_policies": {p["key"]: p["published_version"] for p in cfg["policies"] if p.get("require_acceptance")},
            "origin_url": BASE, "source": "website", "photos": []}


# --- Full upfront payment ---
class TestFullPayment:
    def test_config_payment_mode(self, cfg):
        assert cfg["business"]["payment_mode"] == "full_upfront"

    def test_preview_deposit_equals_total(self):
        r = requests.post(f"{PUB}/quote/preview", json={"service": "regular", "bedrooms": 2, "bathrooms": 1, "postcode": "SW1A 1AA"})
        assert r.status_code == 200
        d = r.json()
        assert d["deposit"] == d["total"], d

    def test_booking_charges_full_total(self, cfg, owner):
        r = requests.post(f"{PUB}/bookings", json=_booking_body(cfg), timeout=60)
        if r.status_code == 422:
            # access method name may differ, retry with known one
            b = _booking_body(cfg)
            b["access"] = {"method": "estate_agency", "agency_name": "TEST_ A", "agency_address": "1 High St"}
            r = requests.post(f"{PUB}/bookings", json=b, timeout=60)
        assert r.status_code == 200, r.text
        bid = r.json()["booking_id"]
        CREATED["bookings"].append(bid)
        assert "checkout.stripe.com" in r.json()["checkout_url"]
        bk = DB.bookings.find_one({"_id": ObjectId(bid)})
        assert bk["deposit_amount"] == bk["total"] and bk["balance_due"] == 0
        tx = DB.payment_transactions.find_one({"booking_id": bid})
        assert tx["amount"] == bk["total"] and tx["kind"] == "booking"
        pytest.iter5_booking = bid


# --- North/East/West/Central London postcodes ---
class TestPostcodes:
    @pytest.mark.parametrize("pc", ["N1 1AA", "E1 6AN", "W1A 1AA", "EC1A 1BB", "NW1 6XE", "WC2N 5DU"])
    def test_postcode_ok(self, pc):
        r = requests.post(f"{PUB}/quote/preview", json={"service": "regular", "bedrooms": 2, "bathrooms": 1, "postcode": pc})
        assert r.status_code == 200
        assert r.json()["status"] == "ok", r.json()


def _wt_body(**over):
    day = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    b = {"establishment": "office", "business_name": f"TEST_ Biz {uuid.uuid4().hex[:4]}",
         "contact": {"name": "TEST_ Contact", "phone": "07700900222", "email": "delivered@resend.dev"},
         "address": "TEST_ 1 Office Road, London", "postcode": "ec1a 1bb",
         "details": {"workstations": "20", "meeting_rooms": "2", "floors": "1"},
         "schedule": {"kind": "ongoing", "frequency": "weekly", "days": ["Mon", "Wed"], "time": "evening", "start_date": "", "notes": ""},
         "visit": {"preferred_date": day, "preferred_time": "10:00", "alt_date": "", "alt_time": "", "access_info": "Reception"},
         "photos": [], "marketing_consent": False}
    b.update(over)
    return b


# --- Public walkthrough requests ---
class TestWalkthroughPublic:
    def test_past_date_422(self):
        b = _wt_body()
        b["visit"]["preferred_date"] = (dt.date.today() - dt.timedelta(days=1)).isoformat()
        r = requests.post(f"{PUB}/walkthroughs", json=b)
        assert r.status_code == 422 and "future" in r.json()["detail"].lower()
        b["visit"]["preferred_date"] = dt.date.today().isoformat()
        assert requests.post(f"{PUB}/walkthroughs", json=b).status_code == 422

    def test_invalid_establishment_422(self):
        assert requests.post(f"{PUB}/walkthroughs", json=_wt_body(establishment="spaceship")).status_code == 422

    def test_missing_contact_422(self):
        b = _wt_body()
        b["contact"]["email"] = "bad"
        assert requests.post(f"{PUB}/walkthroughs", json=b).status_code == 422

    def test_create_with_photos(self, owner):
        up = requests.post(f"{PUB}/photos", files={"file": ("p.jpg", _img(), "image/jpeg")}, timeout=60).json()
        CREATED["photos"].append(up["id"])
        r = requests.post(f"{PUB}/walkthroughs", json=_wt_body(photos=[{"id": up["id"], "token": up["token"]}]))
        assert r.status_code == 200, r.text
        wid = r.json()["id"]
        CREATED["walkthroughs"].append(wid)
        g = owner.get(f"{BASE}/api/admin/walkthroughs/{wid}")
        assert g.status_code == 200
        w = g.json()["walkthrough"]
        assert w["status"] == "requested" and w["availability_note"]
        assert w["postcode"] == "EC1A 1BB" and w["establishment_name"] == "Office"
        assert w["details"]["workstations"] == "20"
        assert "_id" not in w
        ph = g.json()["photos"]
        assert [p["id"] for p in ph] == [up["id"]]
        assert all("token" not in p and "path" not in p for p in ph)
        assert DB.photos.find_one({"_id": ObjectId(up["id"])})["walkthrough_id"] == wid
        # owner can view walkthrough photo file
        f = owner.get(f"{BASE}/api/admin/bookings/photos/{up['id']}/file")
        assert f.status_code == 200 and f.content[:2] == b"\xff\xd8"
        lst = owner.get(f"{BASE}/api/admin/walkthroughs").json()
        assert any(x["id"] == wid for x in lst)
        pytest.wid = wid


# --- Admin walkthrough management (owner only) ---
class TestWalkthroughAdmin:
    def test_anonymous_401(self):
        assert requests.get(f"{BASE}/api/admin/walkthroughs").status_code == 401
        assert requests.patch(f"{BASE}/api/admin/walkthroughs/{pytest.wid}", json={"status": "declined"}).status_code == 401

    def test_confirm_requires_date_time(self, owner):
        r = owner.patch(f"{BASE}/api/admin/walkthroughs/{pytest.wid}", json={"status": "confirmed"})
        assert r.status_code == 422
        day = (dt.date.today() + dt.timedelta(days=6)).isoformat()
        r = owner.patch(f"{BASE}/api/admin/walkthroughs/{pytest.wid}", json={"status": "confirmed", "confirmed_date": day, "confirmed_time": "11:00"})
        assert r.status_code == 200
        w = owner.get(f"{BASE}/api/admin/walkthroughs/{pytest.wid}").json()["walkthrough"]
        assert w["status"] == "confirmed" and w["confirmed_date"] == day and w["confirmed_time"] == "11:00"
        assert any("confirmed" in h["text"].lower() for h in w["history"])

    def test_alternative_requires_message(self, owner):
        assert owner.patch(f"{BASE}/api/admin/walkthroughs/{pytest.wid}", json={"status": "alternative_proposed", "message": "  "}).status_code == 422
        r = owner.patch(f"{BASE}/api/admin/walkthroughs/{pytest.wid}", json={"status": "alternative_proposed", "message": "TEST_ How about Friday 2pm?"})
        assert r.status_code == 200
        assert owner.get(f"{BASE}/api/admin/walkthroughs/{pytest.wid}").json()["walkthrough"]["status"] == "alternative_proposed"

    def test_complete_decline_invalid(self, owner):
        for st in ("completed", "declined"):
            assert owner.patch(f"{BASE}/api/admin/walkthroughs/{pytest.wid}", json={"status": st}).status_code == 200
            assert owner.get(f"{BASE}/api/admin/walkthroughs/{pytest.wid}").json()["walkthrough"]["status"] == st
        assert owner.patch(f"{BASE}/api/admin/walkthroughs/{pytest.wid}", json={"status": "bogus"}).status_code == 400
        assert owner.get(f"{BASE}/api/admin/walkthroughs/{'0' * 24}").status_code == 404


# --- Before/after job photos + staff scoping ---
class TestJobPhotos:
    def _up(self, sess, bid, kind="before"):
        return sess.post(f"{BASE}/api/admin/bookings/{bid}/photos", data={"kind": kind}, files={"file": ("j.jpg", _img((200, 10, 10)), "image/jpeg")}, timeout=60)

    def test_anonymous_401(self):
        r = requests.post(f"{BASE}/api/admin/bookings/{pytest.iter5_booking}/photos", data={"kind": "before"}, files={"file": ("j.jpg", _img(), "image/jpeg")})
        assert r.status_code == 401

    def test_invalid_kind_422(self, owner):
        assert self._up(owner, pytest.iter5_booking, "during").status_code == 422

    def test_non_image_415(self, owner):
        r = owner.post(f"{BASE}/api/admin/bookings/{pytest.iter5_booking}/photos", data={"kind": "after"}, files={"file": ("x.txt", b"nope", "text/plain")})
        assert r.status_code == 415

    def test_owner_upload_before_after(self, owner):
        bid = pytest.iter5_booking
        for k in ("before", "after"):
            r = self._up(owner, bid, k)
            assert r.status_code == 200, r.text
            CREATED["photos"].append(r.json()["id"])
        rows = owner.get(f"{BASE}/api/admin/bookings/{bid}/photos").json()
        kinds = sorted(p.get("kind") for p in rows)
        assert kinds == ["after", "before"]
        assert all(p.get("uploaded_by") for p in rows)

    def test_staff_scope(self, owner):
        email = f"test_cleaner_{uuid.uuid4().hex[:6]}@example.com"
        r = owner.post(f"{BASE}/api/admin/staff", json={"name": "TEST_Cleaner5", "email": email, "password": "Testpass123", "job_role": "Cleaner"})
        assert r.status_code == 200, r.text
        uid = r.json()["id"]
        CREATED["staff"].append(uid)
        bid = pytest.iter5_booking
        staff = _login({"email": email, "password": "Testpass123"})
        # staff: walkthroughs forbidden
        assert staff.get(f"{BASE}/api/admin/walkthroughs").status_code == 403
        assert staff.patch(f"{BASE}/api/admin/walkthroughs/{pytest.wid}", json={"status": "requested"}).status_code == 403
        # staff not assigned -> 404
        assert self._up(staff, bid).status_code == 404
        assert owner.patch(f"{BASE}/api/admin/bookings/{bid}", json={"assigned_to": uid}).status_code == 200
        r = self._up(staff, bid, "after")
        assert r.status_code == 200, r.text
        CREATED["photos"].append(r.json()["id"])
        owner.patch(f"{BASE}/api/admin/bookings/{bid}", json={"assigned_to": ""})


def teardown_module(module):
    for bid in CREATED["bookings"]:
        DB.bookings.delete_one({"_id": ObjectId(bid)})
        DB.payment_transactions.delete_many({"booking_id": bid})
        DB.photos.delete_many({"booking_id": bid})
    for wid in CREATED["walkthroughs"]:
        DB.walkthroughs.delete_one({"_id": ObjectId(wid)})
        DB.photos.delete_many({"walkthrough_id": wid})
    for pid in CREATED["photos"]:
        DB.photos.delete_one({"_id": ObjectId(pid)})
    for uid in CREATED["staff"]:
        DB.users.delete_one({"_id": ObjectId(uid)})
    print("CREATED", CREATED)
