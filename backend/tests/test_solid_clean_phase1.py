"""Phase 1 Solid Clean testing: service catalogue, pricing, policies, SaaS gate.

Prefix test data with TEST_. Restores all mutations.
"""
import copy
import os
import time
import uuid

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://solid-clean-ai.preview.emergentagent.com").rstrip("/")
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


# ---------- SaaS sign-ups closed ----------
def test_saas_status_closed():
    r = requests.get(f"{BASE}/api/saas/status", timeout=10)
    assert r.status_code == 200
    assert r.json()["signup_enabled"] is False


def test_signup_blocked():
    r = requests.post(f"{BASE}/api/auth/signup", json={
        "company_name": "TEST_Blocked", "name": "T", "email": f"TEST_{uuid.uuid4().hex[:6]}@example.com",
        "password": "Testpass123", "country": "GB"}, timeout=10)
    assert r.status_code == 403


def test_platform_toggle_saas_and_revert(platform):
    # toggle on
    r = platform.patch(f"{BASE}/api/platform/settings", json={"signup_enabled": True})
    assert r.status_code == 200
    assert requests.get(f"{BASE}/api/saas/status").json()["signup_enabled"] is True
    # revert
    r = platform.patch(f"{BASE}/api/platform/settings", json={"signup_enabled": False})
    assert r.status_code == 200
    assert requests.get(f"{BASE}/api/saas/status").json()["signup_enabled"] is False


# ---------- Public config / brand ----------
def test_public_config_branding():
    r = requests.get(f"{BASE}/api/public/solid-clean/config", timeout=10)
    assert r.status_code == 200
    biz = r.json()["business"]
    assert biz["phone"] == "020 3728 4419"
    assert biz["logo_url"] == "/brand/solidclean-logo.png"
    assert biz["brand_primary"] == "#023F00"
    assert biz["brand_accent"] == "#8F7E22"


def test_no_airbnb_or_parking_in_pricing():
    r = requests.get(f"{BASE}/api/public/solid-clean/config", timeout=10)
    body = r.text.lower()
    assert "airbnb" not in body
    assert "parking" not in body


# ---------- Settings read/write + price history + audit log ----------
@pytest.fixture
def settings_snapshot(owner):
    r = owner.get(f"{BASE}/api/admin/settings", timeout=10)
    assert r.status_code == 200
    original = r.json()
    yield owner, original
    # restore on teardown
    body = {k: original[k] for k in ("business", "pricing", "availability", "knowledge_base")}
    owner.put(f"{BASE}/api/admin/settings", json=body, timeout=15)


def test_edit_service_price_creates_history_and_audit(settings_snapshot):
    owner, orig = settings_snapshot
    pricing = copy.deepcopy(orig["pricing"])
    svc = next(s for s in pricing["services"] if s["key"] == "regular")
    old_base = svc["base"]
    svc["base"] = old_base + 7
    body = {"business": orig["business"], "pricing": pricing, "availability": orig["availability"], "knowledge_base": orig["knowledge_base"]}
    r = owner.put(f"{BASE}/api/admin/settings", json=body, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["pricing_changes"] >= 1
    # public preview reflects new base
    q = requests.post(f"{BASE}/api/public/solid-clean/quote/preview", json={
        "service": "regular", "property_type": "flat", "bedrooms": 0, "bathrooms": 0, "living_rooms": 0,
        "condition": "good", "extras": [], "postcode": "SW19 2AB"}, timeout=10).json()
    base_line = next(l for l in q["lines"] if "base" in l["label"].lower())
    assert base_line["amount"] == old_base + 7
    # history
    ph = owner.get(f"{BASE}/api/admin/price-history").json()
    assert any(any(c["field"].endswith("base") and c["new"] == old_base + 7 for c in h["changes"]) for h in ph)
    # audit log
    al = owner.get(f"{BASE}/api/admin/audit-log").json()
    assert any(a["action"] == "settings.update" for a in al)


# ---------- Service duplicate/activate/deactivate/pricing modes ----------
def test_duplicate_activate_online_toggle_and_remove(settings_snapshot):
    owner, orig = settings_snapshot
    pricing = copy.deepcopy(orig["pricing"])
    # duplicate 'regular'
    reg = next(s for s in pricing["services"] if s["key"] == "regular")
    key = f"TEST_dup_{uuid.uuid4().hex[:4]}"
    dup = {**reg, "key": key, "name": "TEST_Regular Copy", "active": False, "pricing_mode": "fixed", "fixed_price": 123.0}
    pricing["services"].append(dup)
    body = {"business": orig["business"], "pricing": pricing, "availability": orig["availability"], "knowledge_base": orig["knowledge_base"]}
    assert owner.put(f"{BASE}/api/admin/settings", json=body).status_code == 200

    # inactive => not in public config
    pub = requests.get(f"{BASE}/api/public/solid-clean/config").json()
    assert not any(s["key"] == key for s in pub["pricing"]["services"] if s.get("active"))

    # preview on inactive -> invalid
    pv = requests.post(f"{BASE}/api/public/solid-clean/quote/preview", json={
        "service": key, "property_type": "flat", "bedrooms": 1, "bathrooms": 1, "living_rooms": 1,
        "condition": "good", "extras": [], "postcode": "SW1A 1AA"}).json()
    assert pv["status"] == "invalid"

    # activate; fixed mode -> single-line
    for s in pricing["services"]:
        if s["key"] == key:
            s["active"] = True
    owner.put(f"{BASE}/api/admin/settings", json=body)
    pv = requests.post(f"{BASE}/api/public/solid-clean/quote/preview", json={
        "service": key, "property_type": "flat", "bedrooms": 2, "bathrooms": 1, "living_rooms": 1,
        "condition": "good", "extras": [], "postcode": "SW1A 1AA"}).json()
    assert pv["status"] == "ok"
    assert pv["total"] == 123.0
    # only one priced line (no per-room expansion)
    priced = [l for l in pv["lines"] if l["amount"]]
    assert len(priced) == 1

    # switch to 'from' -> needs_review
    for s in pricing["services"]:
        if s["key"] == key:
            s["pricing_mode"] = "from"
    owner.put(f"{BASE}/api/admin/settings", json=body)
    pv = requests.post(f"{BASE}/api/public/solid-clean/quote/preview", json={
        "service": key, "property_type": "flat", "bedrooms": 1, "bathrooms": 1, "living_rooms": 1,
        "condition": "good", "extras": [], "postcode": "SW1A 1AA"}).json()
    assert pv["status"] == "needs_review"

    # turn online_booking off -> invalid on public
    for s in pricing["services"]:
        if s["key"] == key:
            s["online_booking"] = False
            s["pricing_mode"] = "fixed"
    owner.put(f"{BASE}/api/admin/settings", json=body)
    pv = requests.post(f"{BASE}/api/public/solid-clean/quote/preview", json={
        "service": key, "property_type": "flat", "bedrooms": 1, "bathrooms": 1, "living_rooms": 1,
        "condition": "good", "extras": [], "postcode": "SW1A 1AA"}).json()
    assert pv["status"] == "invalid"


# ---------- Promo codes + short-notice ----------
def test_promo_and_short_notice(settings_snapshot):
    owner, orig = settings_snapshot
    pricing = copy.deepcopy(orig["pricing"])
    pricing["promo_codes"] = [{"code": "TEST10", "type": "percent", "value": 10, "expires": "", "max_uses": 0, "uses": 0, "active": True}]
    pricing["short_notice"] = {"days": 2, "type": "percent", "value": 20}
    body = {"business": orig["business"], "pricing": pricing, "availability": orig["availability"], "knowledge_base": orig["knowledge_base"]}
    assert owner.put(f"{BASE}/api/admin/settings", json=body).status_code == 200

    # valid promo
    pv = requests.post(f"{BASE}/api/public/solid-clean/quote/preview", json={
        "service": "regular", "property_type": "flat", "bedrooms": 2, "bathrooms": 1, "living_rooms": 1,
        "condition": "good", "extras": [], "postcode": "SW1A 1AA", "promo_code": "TEST10"}).json()
    assert pv.get("promo_applied") == "TEST10"
    assert any("Promo TEST10" in l["label"] and l["amount"] < 0 for l in pv["lines"])

    # invalid
    pv = requests.post(f"{BASE}/api/public/solid-clean/quote/preview", json={
        "service": "regular", "property_type": "flat", "bedrooms": 2, "bathrooms": 1, "living_rooms": 1,
        "condition": "good", "extras": [], "postcode": "SW1A 1AA", "promo_code": "BADCODE"}).json()
    assert pv.get("promo_error") == "Promo code not valid"

    # short-notice (today -> within window)
    import datetime as dt
    today = dt.date.today().isoformat()
    pv = requests.post(f"{BASE}/api/public/solid-clean/quote/preview", json={
        "service": "regular", "property_type": "flat", "bedrooms": 2, "bathrooms": 1, "living_rooms": 1,
        "condition": "good", "extras": [], "postcode": "SW1A 1AA", "date": today}).json()
    assert any("Short-notice" in l["label"] for l in pv["lines"])


# ---------- Policies ----------
def test_policies_list_count(owner):
    r = owner.get(f"{BASE}/api/admin/policies").json()
    assert len(r) == 14


def test_policy_publish_blocked_with_markers(owner):
    r = owner.post(f"{BASE}/api/admin/policies/booking/publish", json={"confirm": True})
    assert r.status_code == 400
    assert "REVIEW REQUIRED" in r.text


def test_policy_publish_success_and_public_visible(owner):
    # property_condition has no [REVIEW REQUIRED] marker in seed
    pols = {p["key"]: p for p in owner.get(f"{BASE}/api/admin/policies").json()}
    pc = pols["property_condition"]
    assert "[REVIEW REQUIRED" not in pc["draft_content"]
    r = owner.post(f"{BASE}/api/admin/policies/property_condition/publish", json={"confirm": True})
    assert r.status_code == 200, r.text
    v = r.json()["version"]
    assert v >= 1
    # public /config shows it
    cfg = requests.get(f"{BASE}/api/public/solid-clean/config").json()
    assert any(p["key"] == "property_condition" and p["published_version"] == v for p in cfg["policies"])


def test_booking_requires_accepted_policies(owner):
    # enable require_acceptance for property_condition
    pols = {p["key"]: p for p in owner.get(f"{BASE}/api/admin/policies").json()}
    pc = pols["property_condition"]
    assert pc["published_version"] >= 1
    r = owner.put(f"{BASE}/api/admin/policies/property_condition", json={
        "title": pc["title"], "draft_content": pc["draft_content"], "needs_review": False,
        "effective_date": pc.get("effective_date") or "", "require_acceptance": True})
    assert r.status_code == 200

    # booking w/o accepted_policies -> 409
    booking_body = {
        "quote": {"service": "regular", "property_type": "flat", "bedrooms": 2, "bathrooms": 1,
                  "living_rooms": 1, "condition": "good", "extras": [], "postcode": "SW1A 1AA"},
        "contact": {"name": "TEST_Buyer", "email": "test_buyer@example.com", "phone": "07700900000", "marketing_consent": False},
        "date": "2099-01-01", "slot": "11:00", "access_notes": "", "accepted_policies": {},
        "origin_url": BASE, "source": "website"}
    r = requests.post(f"{BASE}/api/public/solid-clean/bookings", json=booking_body, timeout=15)
    assert r.status_code == 409, f"expected 409, got {r.status_code} {r.text}"

    # revert require_acceptance
    owner.put(f"{BASE}/api/admin/policies/property_condition", json={
        "title": pc["title"], "draft_content": pc["draft_content"], "needs_review": False,
        "effective_date": pc.get("effective_date") or "", "require_acceptance": False})


# ---------- Staff role gating ----------
def test_staff_cannot_write_settings_or_publish_policies(owner):
    # create TEST_ staff
    staff_email = f"test_staff_{uuid.uuid4().hex[:6]}@example.com"
    r = owner.post(f"{BASE}/api/admin/staff", json={
        "name": "TEST_Staff", "email": staff_email, "password": "Testpass123", "job_role": "Cleaner"})
    if r.status_code == 403:
        pytest.skip(f"cannot add staff (plan limit): {r.text}")
    assert r.status_code == 200, r.text
    staff_uid = r.json()["id"]

    try:
        staff = _login({"email": staff_email, "password": "Testpass123"})
        orig = owner.get(f"{BASE}/api/admin/settings").json()
        body = {k: orig[k] for k in ("business", "pricing", "availability", "knowledge_base")}
        r = staff.put(f"{BASE}/api/admin/settings", json=body)
        assert r.status_code == 403
        r = staff.post(f"{BASE}/api/admin/policies/property_condition/publish", json={"confirm": True})
        assert r.status_code == 403
    finally:
        # deactivate test staff
        owner.patch(f"{BASE}/api/admin/staff/{staff_uid}", json={"active": False})
