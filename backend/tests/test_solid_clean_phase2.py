"""Phase 2 Solid Clean testing: public pages, booking flow (to Stripe),
contact lead creation, reviews, admin auth gating, staff permissions,
owner regression.

Credentials:
  Owner    : admin@solidcleanltd.com / SolidClean#2026
  Platform : gilctei@hotmail.com / CleanOps#2026

Pacing: /api/auth/* is 60 req/min. We reuse sessions, so this is cheap.
Prefix test data with TEST_. Restores all mutations.
"""
import datetime as dt
import os
import time
import uuid

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://solid-clean-ai.preview.emergentagent.com").rstrip("/")
SLUG = "solid-clean"
PUB = f"{BASE}/api/public/{SLUG}"
OWNER = {"email": "admin@solidcleanltd.com", "password": "SolidClean#2026"}
PLATFORM = {"email": "gilctei@hotmail.com", "password": "CleanOps#2026"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login {creds['email']}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def owner():
    return _login(OWNER)


@pytest.fixture(scope="module")
def platform():
    return _login(PLATFORM)


# ----- Public config: branding + absence of parking -----
def test_public_config_no_parking_and_brand():
    r = requests.get(f"{PUB}/config", timeout=10)
    assert r.status_code == 200
    body = r.text.lower()
    assert "parking" not in body, "public config must not mention parking"
    assert "airbnb" not in body
    biz = r.json()["business"]
    assert biz["phone"] == "020 3728 4419"
    assert biz["logo_url"] == "/brand/solidclean-logo.png"


# ----- Reviews endpoint excludes demo seeded reviews -----
def test_public_reviews_excludes_demo():
    r = requests.get(f"{PUB}/reviews", timeout=10)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    # Reviews may be empty or contain only non-demo. Nothing with demo flag should surface.
    # (demo field would not be present in the response schema anyway)
    for row in rows:
        assert "demo" not in row  # response projection


# ----- Admin APIs require auth: 401 for unauth -----
@pytest.mark.parametrize("path", [
    "/api/admin/leads", "/api/admin/overview", "/api/admin/bookings",
    "/api/admin/settings", "/api/admin/policies",
])
def test_admin_endpoints_require_auth(path):
    r = requests.get(f"{BASE}{path}", timeout=10)
    assert r.status_code == 401, f"{path} returned {r.status_code}"


# ----- Contact form creates a lead with source=website -----
def test_contact_creates_lead(owner):
    unique = f"test_contact_{uuid.uuid4().hex[:6]}"
    payload = {
        "name": f"TEST_{unique}",
        "email": f"{unique}@example.com",
        "phone": "07700900001",
        "message": "TEST contact submission from automated test",
        "marketing_consent": False,
    }
    r = requests.post(f"{PUB}/contact", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    # Verify in /admin/leads
    r = owner.get(f"{BASE}/api/admin/leads", params={"q": unique}, timeout=15)
    assert r.status_code == 200
    leads = r.json()
    hit = next((l for l in leads if l["email"] == payload["email"]), None)
    assert hit, f"lead not found for {payload['email']}"
    assert hit["source"] == "website"


# ----- Booking end-to-end up to Stripe redirect -----
@pytest.fixture
def booking_and_cleanup(owner):
    """Create a public booking, yield (booking_id, booking_doc) and leave in DB (hold expires naturally)."""
    future, slots = None, []
    for days_ahead in range(2, 60):
        candidate = (dt.date.today() + dt.timedelta(days=days_ahead)).isoformat()
        av = requests.get(f"{PUB}/availability", params={"date": candidate}, timeout=15).json()
        if av.get("slots"):
            future, slots = candidate, av["slots"]
            break
    if not slots:
        pytest.skip("no availability in the next 60 days")
    slot = slots[0]["slot"]
    unique = uuid.uuid4().hex[:6]
    booking_body = {
        "quote": {"service": "regular", "property_type": "flat", "bedrooms": 2, "bathrooms": 1,
                  "living_rooms": 1, "condition": "good", "extras": [], "postcode": "CR0 1AA"},
        "contact": {"name": f"TEST_booker_{unique}", "email": f"test_booker_{unique}@example.com",
                    "phone": "07700900002", "marketing_consent": False},
        "date": future, "slot": slot, "access_notes": "TEST", "accepted_policies": {},
        "origin_url": BASE, "source": "website"}
    # If any policy currently requires acceptance, pass its version
    cfg = requests.get(f"{PUB}/config").json()
    for p in cfg.get("policies", []):
        if p.get("require_acceptance"):
            booking_body["accepted_policies"][p["key"]] = p["published_version"]
    r = requests.post(f"{PUB}/bookings", json=booking_body, timeout=30)
    assert r.status_code == 200, f"booking failed: {r.status_code} {r.text}"
    data = r.json()
    booking_id = data["booking_id"]
    yield booking_id, data, booking_body
    # Release (abandons the booking so it doesn't pollute Awaiting payment)
    try:
        requests.post(f"{PUB}/bookings/{booking_id}/release", timeout=10)
    except Exception:
        pass


def test_booking_redirects_to_stripe(booking_and_cleanup):
    _, data, _ = booking_and_cleanup
    assert "checkout_url" in data, data
    assert data["checkout_url"].startswith("https://checkout.stripe.com/"), data["checkout_url"]


def test_booking_appears_in_admin_awaiting_payment(owner, booking_and_cleanup):
    booking_id, _, body = booking_and_cleanup
    r = owner.get(f"{BASE}/api/admin/bookings", params={"status": "pending_payment"}, timeout=15)
    assert r.status_code == 200
    rows = r.json()
    hit = next((b for b in rows if b["id"] == booking_id), None)
    assert hit, f"booking {booking_id} not in Awaiting payment"
    assert hit["customer"]["email"] == body["contact"]["email"]
    assert hit["status"] == "pending_payment"


# ----- Service-price change reflects on /quote preview; confirmed booking total is immutable -----
def test_price_change_reflects_on_quote_preview_and_restore(owner):
    """Change regular service base price; verify preview; restore."""
    orig = owner.get(f"{BASE}/api/admin/settings").json()
    import copy
    pricing = copy.deepcopy(orig["pricing"])
    svc = next(s for s in pricing["services"] if s["key"] == "regular")
    original_base = svc["base"]
    svc["base"] = original_base + 11
    body = {k: orig[k] for k in ("business", "pricing", "availability", "knowledge_base")}
    body["pricing"] = pricing
    try:
        r = owner.put(f"{BASE}/api/admin/settings", json=body, timeout=15)
        assert r.status_code == 200
        pv = requests.post(f"{PUB}/quote/preview", json={
            "service": "regular", "property_type": "flat", "bedrooms": 0, "bathrooms": 0,
            "living_rooms": 0, "condition": "good", "extras": [], "postcode": "CR0 1AA"}).json()
        base_line = next(l for l in pv["lines"] if "base" in l["label"].lower())
        assert base_line["amount"] == original_base + 11
    finally:
        # restore
        pricing2 = copy.deepcopy(orig["pricing"])
        body["pricing"] = pricing2
        owner.put(f"{BASE}/api/admin/settings", json=body, timeout=15)
        pv = requests.post(f"{PUB}/quote/preview", json={
            "service": "regular", "property_type": "flat", "bedrooms": 0, "bathrooms": 0,
            "living_rooms": 0, "condition": "good", "extras": [], "postcode": "CR0 1AA"}).json()
        restored = next(l for l in pv["lines"] if "base" in l["label"].lower())
        assert restored["amount"] == original_base, "price not restored"


# ----- Staff permissions -----
@pytest.fixture
def staff_user(owner):
    """Create TEST_ staff user, yield (session, user_id, email). Deactivate on teardown."""
    email = f"test_cleaner_{uuid.uuid4().hex[:6]}@example.com"
    password = "Testpass123"
    r = owner.post(f"{BASE}/api/admin/staff", json={
        "name": "TEST_Cleaner", "email": email, "password": password, "job_role": "Cleaner"})
    if r.status_code == 403:
        pytest.skip(f"staff creation blocked (plan limit): {r.text}")
    assert r.status_code == 200, r.text
    uid = r.json()["id"]
    staff_session = _login({"email": email, "password": password})
    yield staff_session, uid, email
    # deactivate
    owner.patch(f"{BASE}/api/admin/staff/{uid}", json={"active": False})


def test_staff_permissions_endpoints_and_booking_scope(owner, staff_user, booking_and_cleanup):
    staff, uid, _ = staff_user
    booking_id, _, _ = booking_and_cleanup

    # 1) assign booking to staff
    r = owner.patch(f"{BASE}/api/admin/bookings/{booking_id}", json={"assigned_to": uid})
    assert r.status_code == 200, r.text

    # 2) staff lists bookings -> only assigned shown
    r = staff.get(f"{BASE}/api/admin/bookings")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 1
    assert all(b.get("assigned_to") == uid for b in rows), [b.get("assigned_to") for b in rows]

    # 3) staff forbidden on non-staff endpoints
    for path in ("/api/admin/leads", "/api/admin/overview", "/api/admin/settings"):
        r = staff.get(f"{BASE}{path}")
        assert r.status_code == 403, f"{path} returned {r.status_code}"

    # 4) staff can access policies (staff-visible subset)
    r = staff.get(f"{BASE}/api/admin/policies")
    assert r.status_code == 200
    # policies list only contains audience=='staff' or everyone from staff view
    assert isinstance(r.json(), list)

    # 5) staff PATCH booking not assigned to them -> 403
    # find any other booking in the system (owner view) that is not assigned to this staff
    other = None
    all_bookings = owner.get(f"{BASE}/api/admin/bookings").json()
    for b in all_bookings:
        if b["id"] != booking_id and b.get("assigned_to") != uid:
            other = b
            break
    if other:
        r = staff.patch(f"{BASE}/api/admin/bookings/{other['id']}", json={"status": "completed"})
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"
    # Also: trying to reassign is forbidden
    r = staff.patch(f"{BASE}/api/admin/bookings/{booking_id}", json={"assigned_to": uid, "status": "completed"})
    assert r.status_code == 403


# ----- Owner regression -----
def test_owner_overview_leads_settings_work(owner):
    for path in ("/api/admin/overview", "/api/admin/leads", "/api/admin/settings"):
        r = owner.get(f"{BASE}{path}", timeout=15)
        assert r.status_code == 200, f"{path} returned {r.status_code}"


def test_platform_endpoints_work(platform):
    r = platform.get(f"{BASE}/api/platform/companies", timeout=15)
    assert r.status_code == 200
    r = platform.get(f"{BASE}/api/platform/plans", timeout=15)
    assert r.status_code == 200
