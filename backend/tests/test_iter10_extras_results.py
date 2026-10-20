"""Iteration 10: per-item extras pricing (extra_qty), booking lines with quantities, before/after job photos,
'send results' email link and public results page security. Creates TEST_ data and cleans it up."""
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
ADM = f"{BASE}/api/admin/bookings"
OWNER = {"email": "admin@solidcleanltd.com", "password": "SolidClean#2026"}
ENV = dotenv_values("/app/backend/.env")
DB = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
CID = "6acb2a20e5d23531c955e49b"
CREATED = {"bookings": [], "staff_emails": [], "emails": []}


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


def _q(**kw):
    q = {"service": "regular", "property_type": "flat", "bedrooms": 2, "bathrooms": 1, "living_rooms": 1, "condition": "good"}
    q.update(kw)
    return requests.post(f"{PUB}/quote/preview", json=q, timeout=20)


def _mk_booking(name="TEST_ Results Customer"):
    email = f"test_res_{uuid.uuid4().hex[:6]}@example.com"
    CREATED["emails"].append(email)
    doc = {"customer": {"name": name, "email": email, "phone": "07700900123"}, "service": "regular",
           "service_name": "Residential / Regular Clean", "date": "2026-12-01", "slot": "10:00", "status": "confirmed",
           "payment_status": "paid", "total": 87.0, "reference": f"TEST-{uuid.uuid4().hex[:5]}", "company_id": CID,
           "created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "lines": []}
    bid = str(DB.bookings.insert_one(doc).inserted_id)
    CREATED["bookings"].append(bid)
    return bid


# --- Per-item extras pricing ---
class TestExtrasPricing:
    def test_config_has_20_extras_and_services_offer_them(self, cfg):
        ex = cfg["pricing"]["extras"]
        assert len(ex) == 20
        keys = {e["key"] for e in ex}
        for k in ("blinds", "windows", "balcony", "conservatory", "garage", "garden_furniture", "wall_washing", "skirting",
                  "mattress", "sofa", "rug", "curtains"):
            assert k in keys
        svcs = {s["key"]: s for s in cfg["pricing"]["services"]}
        for s in ("regular", "end_of_tenancy"):
            assert set(svcs[s]["extras"]) >= {"conservatory", "mattress", "blinds", "curtains"}

    def test_example_total_219(self):
        r = _q(extras=["blinds", "conservatory", "mattress"], extra_qty={"blinds": 4, "mattress": 2})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total"] == 219
        lab = {l["label"]: l["amount"] for l in d["lines"]}
        assert lab["Blinds cleaning × 4"] == 32
        assert lab["Mattress cleaning × 2"] == 60
        assert lab["Conservatory clean"] == 40

    def test_per_item_prices(self):
        exp = {"blinds": (8, 30), "windows": (5, 40), "balcony": (25, 5), "wall_washing": (20, 15), "skirting": (10, 15),
               "mattress": (30, 10), "sofa": (45, 6), "rug": (25, 10), "curtains": (15, 15)}
        base = _q().json()["total"]
        for k, (price, mx) in exp.items():
            d = _q(extras=[k], extra_qty={k: 3}).json()
            assert d["total"] == base + price * 3, k
            # clamp to max
            d = _q(extras=[k], extra_qty={k: 999}).json()
            assert d["total"] == base + price * mx, f"{k} max clamp"
            # clamp to 1
            for v in (0, -5):
                d = _q(extras=[k], extra_qty={k: v}).json()
                assert d["total"] == base + price, f"{k} min clamp {v}"

    def test_flat_extras_ignore_qty(self):
        base = _q().json()["total"]
        for k, p in (("conservatory", 40), ("garage", 35), ("garden_furniture", 20), ("oven", 45)):
            d = _q(extras=[k], extra_qty={k: 5}).json()
            assert d["total"] == base + p
            assert any(l["label"].endswith(("clean", "Garden furniture clean")) or "×" not in l["label"] for l in d["lines"])
            assert not any("×" in l["label"] for l in d["lines"])

    def test_default_qty_1_and_multipliers(self):
        d = _q(extras=["blinds"]).json()
        assert "Blinds cleaning × 1" in [l["label"] for l in d["lines"]]
        h = _q(property_type="house", condition="poor", extras=["blinds"], extra_qty={"blinds": 2}).json()
        rooms = 87 * 1.12 * 1.35
        assert abs(h["total"] - round(rooms + 16, 2)) < 0.02, h

    def test_min_price_and_eot(self):
        d = _q(bedrooms=0, bathrooms=0, living_rooms=0, extras=["curtains"], extra_qty={"curtains": 1}).json()
        assert d["total"] == 60  # min price top-up still applies
        e = _q(service="end_of_tenancy", extras=["sofa", "garage"], extra_qty={"sofa": 2}).json()
        lab = {l["label"]: l["amount"] for l in e["lines"]}
        assert lab["Sofa / upholstery cleaning × 2"] == 90 and lab["Garage clean"] == 35

    def test_bad_qty_type_422(self):
        r = _q(extras=["blinds"], extra_qty={"blinds": "abc"})
        assert r.status_code == 422


# --- Booking stores qty lines ---
class TestBookingLines:
    def test_booking_with_extra_qty(self, cfg, owner):
        day = slot = None
        for n in range(3, 60):
            dd = (dt.date.today() + dt.timedelta(days=n)).isoformat()
            sl = requests.get(f"{PUB}/availability", params={"date": dd}, timeout=15).json().get("slots")
            if sl:
                day, slot = dd, sl[0]["slot"]
                break
        if not day:
            pytest.skip("no availability")
        email = f"test_bk_{uuid.uuid4().hex[:6]}@example.com"
        CREATED["emails"].append(email)
        body = {"quote": {"service": "regular", "property_type": "flat", "bedrooms": 2, "bathrooms": 1, "living_rooms": 1,
                          "condition": "good", "extras": ["blinds", "conservatory", "mattress"], "extra_qty": {"blinds": 4, "mattress": 2},
                          "postcode": "SW1A 1AA", "address": "TEST_ 10 Test Street, London"},
                "contact": {"name": "TEST_ Qty Booker", "email": email, "phone": "07700900111"},
                "date": day, "slot": slot, "access": {"method": "customer_present"},
                "accepted_policies": {p["key"]: p["published_version"] for p in cfg["policies"] if p.get("require_acceptance")},
                "pay_terms_accepted": True, "origin_url": BASE, "source": "website", "photos": []}
        r = requests.post(f"{PUB}/bookings", json=body, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        CREATED["bookings"].append(d["booking_id"])
        assert "checkout.stripe.com" in d["checkout_url"]
        b = DB.bookings.find_one({"_id": ObjectId(d["booking_id"])})
        labels = {l["label"]: l["amount"] for l in b["lines"]}
        assert labels.get("Blinds cleaning × 4") == 32 and labels.get("Mattress cleaning × 2") == 60
        # total may include short-notice surcharge depending on day; base check
        assert b["total"] >= 219
        if not any("Short-notice" in l for l in labels):
            assert b["total"] == 219


# --- Before/after photos + send results + public results ---
class TestResults:
    def test_upload_kinds_and_send(self, owner):
        bid = _mk_booking()
        # invalid kind
        r = owner.post(f"{ADM}/{bid}/photos", data={"kind": "customer"}, files={"file": ("a.jpg", _img(), "image/jpeg")})
        assert r.status_code == 422
        # send with no after photos -> 400
        assert owner.post(f"{ADM}/{bid}/results/send").status_code == 400
        rb = owner.post(f"{ADM}/{bid}/photos", data={"kind": "before"}, files={"file": ("b.jpg", _img((200, 0, 0)), "image/jpeg")})
        assert rb.status_code == 200, rb.text
        assert owner.post(f"{ADM}/{bid}/results/send").status_code == 400  # before only
        ra = owner.post(f"{ADM}/{bid}/photos", data={"kind": "after"}, files={"file": ("a.jpg", _img((0, 200, 0)), "image/jpeg")})
        assert ra.status_code == 200
        ph = owner.get(f"{ADM}/{bid}/photos").json()
        assert {p["kind"] for p in ph} == {"before", "after"}
        s = owner.post(f"{ADM}/{bid}/results/send")
        assert s.status_code == 200, s.text
        d = s.json()
        assert f"/results/{bid}?t=" in d["url"] and "email_status" in d
        token = d["url"].split("t=")[1]
        # token stable on resend
        assert owner.post(f"{ADM}/{bid}/results/send").json()["url"] == d["url"]
        email = DB.bookings.find_one({"_id": ObjectId(bid)})["customer"]["email"]
        comm = DB.communications.find_one({"template": "job_results", "to": email})
        assert comm is not None, "job_results comm not logged"
        pytest.res = (bid, token, rb.json()["id"], ra.json()["id"])

    def test_public_results(self):
        bid, token, before_id, after_id = pytest.res
        r = requests.get(f"{PUB}/photos/results/{bid}", params={"t": token})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["first_name"] == "TEST_" and {p["kind"] for p in d["photos"]} == {"before", "after"}
        assert "email" not in r.text.lower() or "@" not in r.text
        img = requests.get(f"{PUB}/photos/results/{bid}/{after_id}", params={"t": token})
        assert img.status_code == 200 and img.content[:2] == b"\xff\xd8"
        assert requests.get(f"{PUB}/photos/results/{bid}", params={"t": "wrong"}).status_code == 404
        assert requests.get(f"{PUB}/photos/results/{bid}/{after_id}", params={"t": "wrong"}).status_code == 404
        assert requests.get(f"{PUB}/photos/results/{bid}").status_code == 422
        assert requests.get(f"{PUB}/photos/results/notanid", params={"t": token}).status_code == 404

    def test_cross_booking_and_customer_photo_blocked(self, owner):
        bid, token, _, _ = pytest.res
        other = _mk_booking("TEST_ Other")
        op = owner.post(f"{ADM}/{other}/photos", data={"kind": "after"}, files={"file": ("a.jpg", _img(), "image/jpeg")}).json()["id"]
        assert requests.get(f"{PUB}/photos/results/{bid}/{op}", params={"t": token}).status_code == 404
        # customer photo (no kind) attached to this booking
        cust = DB.photos.insert_one({"path": "x", "status": "attached", "booking_id": bid, "is_deleted": False, "company_id": CID,
                                     "created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "TEST_": True}).inserted_id
        assert requests.get(f"{PUB}/photos/results/{bid}/{cust}", params={"t": token}).status_code == 404
        d = requests.get(f"{PUB}/photos/results/{bid}", params={"t": token}).json()
        assert str(cust) not in [p["id"] for p in d["photos"]]
        # other booking without token -> 404 with token of first
        assert requests.get(f"{PUB}/photos/results/{other}", params={"t": token}).status_code == 404

    def test_staff_scope_and_owner_only_send(self, owner):
        bid = pytest.res[0]
        email = f"test_cleaner_{uuid.uuid4().hex[:6]}@example.com"
        CREATED["staff_emails"].append(email)
        r = owner.post(f"{BASE}/api/admin/staff", json={"name": "TEST_Cleaner", "email": email, "password": "Testpass123", "job_role": "Cleaner"})
        if r.status_code == 403:
            pytest.skip(r.text)
        assert r.status_code == 200, r.text
        uid = r.json()["id"]
        staff = _login({"email": email, "password": "Testpass123"})
        up = lambda: staff.post(f"{ADM}/{bid}/photos", data={"kind": "after"}, files={"file": ("a.jpg", _img(), "image/jpeg")})
        assert up().status_code == 404
        assert staff.get(f"{ADM}/{bid}/photos").status_code == 404
        assert owner.patch(f"{ADM}/{bid}", json={"assigned_to": uid}).status_code == 200
        assert up().status_code == 200
        assert staff.get(f"{ADM}/{bid}/photos").status_code == 200
        assert staff.post(f"{ADM}/{bid}/results/send").status_code == 403
        assert requests.post(f"{ADM}/{bid}/results/send").status_code == 401


def teardown_module(module):
    bids = CREATED["bookings"]
    for bid in bids:
        try:
            requests.post(f"{PUB}/bookings/{bid}/release", timeout=10)
        except Exception:
            pass
    leads = [b.get("lead_id") for b in DB.bookings.find({"_id": {"$in": [ObjectId(b) for b in bids]}}) if b.get("lead_id")]
    DB.photos.delete_many({"booking_id": {"$in": bids}})
    DB.payment_transactions.delete_many({"booking_id": {"$in": bids}})
    DB.quotes.delete_many({"lead_id": {"$in": leads}})
    DB.bookings.delete_many({"_id": {"$in": [ObjectId(b) for b in bids]}})
    DB.leads.delete_many({"_id": {"$in": [ObjectId(x) for x in leads]}})
    DB.communications.delete_many({"$or": [{"lead_id": {"$in": leads}}, {"to": {"$in": CREATED["emails"]}}]})
    DB.users.delete_many({"email": {"$in": CREATED["staff_emails"]}})
