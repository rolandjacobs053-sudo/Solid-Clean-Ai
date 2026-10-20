"""Iteration 4: photo upload, 8-step booking (access, deposit 50%), quote preview extras rules,
photo security (admin/staff scoping). Uses delivered@resend.dev; TEST_ prefix; releases bookings on teardown."""
import datetime as dt
import io
import os
import uuid

import pytest
import requests
from PIL import Image

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
SLUG = "solid-clean"
PUB = f"{BASE}/api/public/{SLUG}"
OWNER = {"email": "admin@solidcleanltd.com", "password": "SolidClean#2026"}
CREATED = {"bookings": [], "photos": [], "staff": []}


def _img(fmt="JPEG", size=(64, 48), color=(10, 120, 30)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, fmt)
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


def _upload(content, name="a.jpg", ctype="image/jpeg"):
    return requests.post(f"{PUB}/photos", files={"file": (name, content, ctype)}, timeout=60)


def _slot():
    for d in range(2, 60):
        day = (dt.date.today() + dt.timedelta(days=d)).isoformat()
        sl = requests.get(f"{PUB}/availability", params={"date": day}, timeout=15).json().get("slots")
        if sl:
            return day, sl[0]["slot"]
    pytest.skip("no availability")


def _booking_body(cfg, **over):
    day, slot = _slot()
    u = uuid.uuid4().hex[:6]
    body = {"quote": {"service": "end_of_tenancy", "property_type": "flat", "bedrooms": 2, "bathrooms": 1, "living_rooms": 1,
                      "condition": "good", "extras": ["freezer_defrost", "fridge", "oven", "oven"], "postcode": "SW1A 1AA",
                      "address": "TEST_ 10 Test Street, London", "furnished": "furnished", "flooring": "carpet", "pets": "yes",
                      "pet_hair_odour": True, "additional_areas": ["garage"]},
            "contact": {"name": f"TEST_booker_{u}", "email": "delivered@resend.dev", "phone": "07700900111"},
            "date": day, "slot": slot, "access": {"method": "estate_agency", "agency_name": "TEST_ Agency", "agency_address": "1 High St",
                                                  "agency_instructions": "Ask for keys at desk"},
            "accepted_policies": {p["key"]: p["published_version"] for p in cfg["policies"] if p.get("require_acceptance")},
            "pay_terms_accepted": True, "origin_url": BASE, "source": "website", "photos": []}
    for k, v in over.items():
        body[k] = v
    return body


# --- Photo upload endpoint ---
class TestPhotoUpload:
    def test_jpeg_and_png_accepted(self):
        for fmt, name, ct in (("JPEG", "t.jpg", "image/jpeg"), ("PNG", "t.png", "image/png")):
            r = _upload(_img(fmt), name, ct)
            assert r.status_code == 200, r.text
            d = r.json()
            assert isinstance(d["id"], str) and d["token"] and d["size"] > 0
            CREATED["photos"].append(d["id"])

    def test_non_image_rejected_415(self):
        r = _upload(b"hello not an image", "x.txt", "text/plain")
        assert r.status_code == 415
        assert "photo" in r.json()["detail"].lower()

    def test_too_large_413(self):
        r = _upload(os.urandom(10 * 1024 * 1024 + 100), "big.jpg", "image/jpeg")
        assert r.status_code == 413


# --- Quote preview pricing rules ---
class TestQuotePreview:
    def test_extras_dedupe_and_freezer_excludes_fridge(self, cfg):
        r = requests.post(f"{PUB}/quote/preview", json={"service": "regular", "bedrooms": 2, "bathrooms": 1,
                                                        "extras": ["oven", "oven", "fridge", "freezer_defrost"]})
        assert r.status_code == 200
        labels = [l["label"] for l in r.json()["lines"]]
        assert labels.count("Single oven deep clean") == 1
        assert "Freezer defrost" in labels and "Fridge/freezer cleaning" not in labels
        d = r.json()
        assert d["deposit"] == round(d["total"] * 0.5, 2)

    def test_extras_prices(self, cfg):
        ex = {e["key"]: e["price"] for e in cfg["pricing"]["extras"]}
        exp = {"oven": 45, "double_oven": 65, "fridge": 25, "dishwasher": 20, "blinds": 20, "windows": 30, "cabinets": 25,
               "balcony": 25, "freezer_defrost": 75, "hob": 25, "supplies": 25}
        for k, v in exp.items():
            assert ex.get(k) == v, f"{k}: {ex.get(k)}"
        assert "parking" not in str(cfg["pricing"]).lower()


# --- Booking creation ---
class TestBooking:
    def test_validation_errors(self, cfg):
        b = _booking_body(cfg)
        b["quote"]["address"] = ""
        assert requests.post(f"{PUB}/bookings", json=b, timeout=30).status_code == 422
        b = _booking_body(cfg, access={"method": "estate_agency", "agency_name": "", "agency_address": ""})
        r = requests.post(f"{PUB}/bookings", json=b, timeout=30)
        assert r.status_code == 422 and "agency" in r.json()["detail"].lower()
        b = _booking_body(cfg, access={"method": "authorised_person", "person_name": "X", "person_phone": ""})
        assert requests.post(f"{PUB}/bookings", json=b, timeout=30).status_code == 422
        b = _booking_body(cfg, accepted_policies={})
        if cfg["policies"] and any(p.get("require_acceptance") for p in cfg["policies"]):
            assert requests.post(f"{PUB}/bookings", json=b, timeout=30).status_code == 409
        b = _booking_body(cfg, accepted_policies={k: v - 1 for k, v in _booking_body(cfg)["accepted_policies"].items()})
        if b["accepted_policies"]:
            assert requests.post(f"{PUB}/bookings", json=b, timeout=30).status_code == 409

    def test_full_booking_with_photos_and_deposit(self, cfg, owner):
        up = [_upload(_img(color=(i * 40, 20, 20))).json() for i in range(2)]
        CREATED["photos"] += [p["id"] for p in up]
        b = _booking_body(cfg, photos=[{"id": p["id"], "token": p["token"]} for p in up] + [{"id": up[0]["id"], "token": "bad"}])
        r = requests.post(f"{PUB}/bookings", json=b, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "checkout.stripe.com" in d["checkout_url"]
        bid = d["booking_id"]
        CREATED["bookings"].append(bid)
        rows = owner.get(f"{BASE}/api/admin/bookings", params={"status": "pending_payment"}).json()
        bk = next(x for x in rows if x["id"] == bid)
        assert bk["deposit_amount"] == round(bk["total"] * 0.5, 2)
        assert bk["balance_due"] == round(bk["total"] - bk["deposit_amount"], 2)
        labels = [l["label"] for l in bk["lines"]]
        assert labels.count("Single oven deep clean") == 1 and "Fridge/freezer cleaning" not in labels
        assert bk["access"]["method"] == "estate_agency" and bk["access"]["agency_name"] == "TEST_ Agency"
        assert bk["address"].startswith("TEST_")
        assert bk["accepted_policies"] == b["accepted_policies"]
        assert bk["input"]["furnished"] == "furnished" and bk["input"]["flooring"] == "carpet"
        # photos attached
        ph = owner.get(f"{BASE}/api/admin/bookings/{bid}/photos")
        assert ph.status_code == 200
        ids = [p["id"] for p in ph.json()]
        assert sorted(ids) == sorted(p["id"] for p in up)
        assert all("token" not in p and "path" not in p for p in ph.json())
        f = owner.get(f"{BASE}/api/admin/bookings/photos/{ids[0]}/file")
        assert f.status_code == 200 and f.headers["content-type"] == "image/jpeg" and f.content[:2] == b"\xff\xd8"
        # lead drawer has photos
        lead = owner.get(f"{BASE}/api/admin/leads/{bk['lead_id']}").json()
        assert len(lead["photos"]) >= 2
        # photo cannot be re-attached by token reuse (already attached)
        b2 = _booking_body(cfg, photos=[{"id": up[0]["id"], "token": up[0]["token"]}])
        r2 = requests.post(f"{PUB}/bookings", json=b2, timeout=60)
        assert r2.status_code == 200
        CREATED["bookings"].append(r2.json()["booking_id"])
        assert owner.get(f"{BASE}/api/admin/bookings/{r2.json()['booking_id']}/photos").json() == []
        pytest.booking_id, pytest.photo_ids = bid, ids

    def test_quote_get_no_address(self, owner):
        bid = pytest.booking_id
        rows = owner.get(f"{BASE}/api/admin/bookings", params={"status": "pending_payment"}).json()
        qid = next(x for x in rows if x["id"] == bid)["quote_id"]
        r = requests.get(f"{PUB}/quotes/{qid}")
        assert r.status_code == 200
        assert "address" not in r.json()["input"]
        assert "TEST_ 10 Test Street" not in r.text


# --- Photo security ---
class TestPhotoSecurity:
    def test_unauthenticated_401(self):
        bid, pid = pytest.booking_id, pytest.photo_ids[0]
        assert requests.get(f"{BASE}/api/admin/bookings/{bid}/photos").status_code == 401
        assert requests.get(f"{BASE}/api/admin/bookings/photos/{pid}/file").status_code == 401

    def test_no_public_photo_route(self):
        pid = pytest.photo_ids[0]
        for u in (f"{PUB}/photos/{pid}", f"{PUB}/photos/{pid}/file", f"{BASE}/api/photos/{pid}"):
            r = requests.get(u)
            assert r.status_code in (404, 405), f"{u}: {r.status_code}"

    def test_staff_scope(self, owner):
        email = f"test_cleaner_{uuid.uuid4().hex[:6]}@example.com"
        r = owner.post(f"{BASE}/api/admin/staff", json={"name": "TEST_Cleaner", "email": email, "password": "Testpass123", "job_role": "Cleaner"})
        if r.status_code == 403:
            pytest.skip(r.text)
        assert r.status_code == 200, r.text
        uid = r.json()["id"]
        CREATED["staff"].append(uid)
        try:
            staff = _login({"email": email, "password": "Testpass123"})
            bid, pid = pytest.booking_id, pytest.photo_ids[0]
            assert staff.get(f"{BASE}/api/admin/bookings/{bid}/photos").status_code == 404
            assert staff.get(f"{BASE}/api/admin/bookings/photos/{pid}/file").status_code == 404
            assert owner.patch(f"{BASE}/api/admin/bookings/{bid}", json={"assigned_to": uid}).status_code == 200
            assert staff.get(f"{BASE}/api/admin/bookings/{bid}/photos").status_code == 200
            assert staff.get(f"{BASE}/api/admin/bookings/photos/{pid}/file").status_code == 200
            owner.patch(f"{BASE}/api/admin/bookings/{bid}", json={"assigned_to": ""})
        finally:
            owner.patch(f"{BASE}/api/admin/staff/{uid}", json={"active": False})


def teardown_module(module):
    for bid in CREATED["bookings"]:
        try:
            requests.post(f"{PUB}/bookings/{bid}/release", timeout=10)
        except Exception:
            pass
    print("CREATED", CREATED)
