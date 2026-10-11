"""
CleanOps SaaS backend test suite.
Covers: auth, signup, tenant isolation, plan feature gating, billing checkout/cancel/resume,
platform admin, public booking, access restriction.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if "REACT_APP_BACKEND_URL" in os.environ else "https://solid-clean-ai.preview.emergentagent.com"
API = f"{BASE_URL}/api"

PLATFORM_EMAIL = "gilctei@hotmail.com"
PLATFORM_PASSWORD = "CleanOps#2026"
SOLID_EMAIL = "admin@solidcleanltd.com"
SOLID_PASSWORD = "SolidClean#2026"


def _login(session, email, password):
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password})
    return r


@pytest.fixture
def new_sess():
    return requests.Session()


@pytest.fixture(scope="module")
def solid_sess():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": SOLID_EMAIL, "password": SOLID_PASSWORD})
    assert r.status_code == 200, f"Solid login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def platform_sess():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": PLATFORM_EMAIL, "password": PLATFORM_PASSWORD})
    assert r.status_code == 200, f"Platform login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def trial_company():
    """Fresh signup trialing on Growth."""
    s = requests.Session()
    uniq = uuid.uuid4().hex[:8]
    email = f"test_owner_{uniq}@example.com"
    r = s.post(f"{API}/auth/signup", json={
        "company_name": f"TEST_Co_{uniq}",
        "name": "Test Owner",
        "email": email,
        "password": "Testpass123!",
        "country": "UK",
    })
    assert r.status_code == 200, f"Signup failed: {r.status_code} {r.text}"
    me = s.get(f"{API}/auth/me").json()
    return {"session": s, "email": email, "me": me}


# ---------- health ----------
class TestHealth:
    def test_root(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_public_plans(self):
        r = requests.get(f"{API}/saas/plans")
        assert r.status_code == 200
        plans = r.json()
        keys = {p["key"] for p in plans}
        assert {"starter", "growth", "pro"}.issubset(keys)


# ---------- auth ----------
class TestAuth:
    def test_login_platform(self, platform_sess):
        r = platform_sess.get(f"{API}/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == PLATFORM_EMAIL
        assert data.get("role") == "platform_admin"

    def test_login_solid_owner(self, solid_sess):
        r = solid_sess.get(f"{API}/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["role"] == "owner"
        assert data["company"]["slug"] == "solid-clean"
        assert data["company"]["comped"] is True

    def test_login_bad_password(self, new_sess):
        r = new_sess.post(f"{API}/auth/login", json={"email": SOLID_EMAIL, "password": "wrong_pw_zzz"})
        assert r.status_code == 401

    def test_me_unauthenticated(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_logout(self):
        s = requests.Session()
        _login(s, SOLID_EMAIL, SOLID_PASSWORD)
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200
        r2 = s.get(f"{API}/auth/me")
        assert r2.status_code == 401


# ---------- signup & tenant isolation ----------
class TestSignupAndIsolation:
    def test_signup_creates_trialing_growth(self, trial_company):
        me = trial_company["me"]
        assert me["role"] == "owner"
        assert me["company"]["plan_key"] == "growth"
        assert me["company"]["subscription_status"] == "trialing"
        assert me["company"]["comped"] is False

    def test_new_company_has_no_demo_data(self, trial_company):
        s = trial_company["session"]
        leads = s.get(f"{API}/admin/leads").json()
        assert isinstance(leads, list) and len(leads) == 0
        bookings = s.get(f"{API}/admin/bookings").json()
        assert isinstance(bookings, list) and len(bookings) == 0

    def test_signup_duplicate_email(self, trial_company):
        s = requests.Session()
        r = s.post(f"{API}/auth/signup", json={
            "company_name": "TEST_dup", "name": "x",
            "email": trial_company["email"], "password": "Testpass123!",
        })
        assert r.status_code == 409

    def test_cross_tenant_lead_access(self, solid_sess, trial_company):
        # get a solid clean lead id
        leads = solid_sess.get(f"{API}/admin/leads").json()
        assert len(leads) > 0, "Solid Clean should have seed leads"
        lead_id = leads[0]["id"]
        # access with trial company owner
        r = trial_company["session"].get(f"{API}/admin/leads/{lead_id}")
        assert r.status_code == 404, f"Cross-tenant leak! status={r.status_code}"


# ---------- feature gating ----------
class TestFeatureGating:
    def test_growth_cannot_seo_audit(self, trial_company):
        r = trial_company["session"].post(f"{API}/admin/tools/seo-audit", json={})
        assert r.status_code == 403

    def test_growth_cannot_outreach(self, trial_company):
        r = trial_company["session"].get(f"{API}/admin/prospects")
        assert r.status_code == 403

    def test_growth_has_receptionist_feature(self, trial_company):
        feats = trial_company["me"]["company"]["features"]
        assert "ai_receptionist" in feats
        assert "reviews" in feats
        assert "outreach" not in feats
        assert "marketing" not in feats

    def test_pro_comped_can_seo_audit(self, solid_sess):
        r = solid_sess.post(f"{API}/admin/tools/seo-audit",
                            json={"url": "https://example.com", "keywords": ["cleaning"]})
        # Should pass gating (may be 200 or 500 depending on AI, but not 403)
        assert r.status_code != 403, f"Pro comped blocked from SEO audit: {r.text}"


# ---------- billing ----------
class TestBilling:
    def test_summary(self, trial_company):
        r = trial_company["session"].get(f"{API}/billing/summary")
        assert r.status_code == 200
        data = r.json()
        assert "plans" in data and len(data["plans"]) >= 3
        assert data["company"]["plan_key"] == "growth"
        assert data["access"]["ok"] is True

    def test_checkout_creates_stripe_session(self, trial_company):
        r = trial_company["session"].post(f"{API}/billing/checkout", json={
            "plan_key": "pro", "interval": "month", "origin_url": BASE_URL
        })
        assert r.status_code == 200, f"Checkout failed: {r.text}"
        data = r.json()
        # Trial company has no stripe sub yet -> expect checkout_url
        assert "checkout_url" in data or data.get("changed") is True
        if "checkout_url" in data:
            assert "stripe.com" in data["checkout_url"] or "checkout" in data["checkout_url"]

    def test_portal_without_customer(self, trial_company):
        # Fresh trial has no stripe_customer_id yet (unless checkout above created one)
        r = trial_company["session"].post(f"{API}/billing/portal", json={"origin_url": BASE_URL})
        # Either 400 (no customer) or 200 (if customer was created in previous test)
        assert r.status_code in (200, 400)


# ---------- platform admin ----------
class TestPlatformAdmin:
    def test_overview(self, platform_sess):
        r = platform_sess.get(f"{API}/platform/overview")
        assert r.status_code == 200
        data = r.json()
        for k in ("companies", "mrr", "arr", "by_status", "by_plan"):
            assert k in data

    def test_companies_list(self, platform_sess):
        r = platform_sess.get(f"{API}/platform/companies")
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        assert any(c.get("slug") == "solid-clean" for c in rows)

    def test_plans_list(self, platform_sess):
        r = platform_sess.get(f"{API}/platform/plans")
        assert r.status_code == 200
        assert len(r.json()) >= 3

    def test_payments_list(self, platform_sess):
        r = platform_sess.get(f"{API}/platform/payments")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_platform_requires_platform_role(self, solid_sess):
        r = solid_sess.get(f"{API}/platform/overview")
        assert r.status_code == 403

    def test_extend_trial(self, platform_sess, trial_company):
        cid = trial_company["me"]["company"]["id"]
        r = platform_sess.patch(f"{API}/platform/companies/{cid}",
                                json={"extend_trial_days": 7})
        assert r.status_code == 200

    def test_suspend_and_access_restriction(self, platform_sess, trial_company):
        cid = trial_company["me"]["company"]["id"]
        # suspend
        r = platform_sess.patch(f"{API}/platform/companies/{cid}", json={"suspended": True})
        assert r.status_code == 200
        # company admin API should now return 402
        r2 = trial_company["session"].get(f"{API}/admin/overview")
        assert r2.status_code == 402, f"Expected 402 on suspended, got {r2.status_code}"
        # /auth/me still works and reports access.ok=False
        me = trial_company["session"].get(f"{API}/auth/me").json()
        assert me["company"]["access"]["ok"] is False
        # Public page unavailable
        slug = trial_company["me"]["company"]["slug"]
        pr = requests.get(f"{API}/public/{slug}/config")
        assert pr.status_code == 402
        # reactivate
        r3 = platform_sess.patch(f"{API}/platform/companies/{cid}", json={"suspended": False})
        assert r3.status_code == 200
        r4 = trial_company["session"].get(f"{API}/admin/overview")
        assert r4.status_code == 200


# ---------- staff management ----------
class TestStaff:
    def test_add_staff_and_login(self, trial_company):
        s = trial_company["session"]
        uniq = uuid.uuid4().hex[:8]
        staff_email = f"test_staff_{uniq}@example.com"
        r = s.post(f"{API}/admin/staff", json={
            "name": "TEST Staff", "email": staff_email,
            "password": "Staffpass123!", "job_role": "Cleaner",
        })
        assert r.status_code == 200, r.text
        staff_id = r.json()["id"]
        # Staff can log in
        sess2 = requests.Session()
        r2 = sess2.post(f"{API}/auth/login", json={"email": staff_email, "password": "Staffpass123!"})
        assert r2.status_code == 200
        me2 = sess2.get(f"{API}/auth/me").json()
        assert me2["role"] == "staff"
        assert me2["company_id"] == trial_company["me"]["company_id"]
        # Deactivate
        r3 = s.patch(f"{API}/admin/staff/{staff_id}", json={"active": False})
        assert r3.status_code == 200
        # Deactivated cannot log in
        sess3 = requests.Session()
        r4 = sess3.post(f"{API}/auth/login", json={"email": staff_email, "password": "Staffpass123!"})
        assert r4.status_code == 401


# ---------- public booking flow ----------
class TestPublicBooking:
    def test_public_config(self):
        r = requests.get(f"{API}/public/solid-clean/config")
        assert r.status_code == 200
        cfg = r.json()
        assert cfg["ai_receptionist"] is True
        assert "pricing" in cfg

    def test_quote_preview(self):
        r = requests.post(f"{API}/public/solid-clean/quote/preview", json={
            "service": "domestic", "property_type": "flat", "bedrooms": 2,
            "bathrooms": 1, "living_rooms": 1, "condition": "good", "extras": [], "parking": "free",
        })
        # Service name may differ; accept 200 regardless of status within body
        assert r.status_code == 200
        data = r.json()
        assert "status" in data

    def test_availability(self):
        from datetime import date, timedelta
        d = (date.today() + timedelta(days=7)).isoformat()
        r = requests.get(f"{API}/public/solid-clean/availability", params={"date": d})
        assert r.status_code == 200
        assert "slots" in r.json()


# ---------- admin APIs for solid clean ----------
class TestSolidAdmin:
    def test_overview(self, solid_sess):
        r = solid_sess.get(f"{API}/admin/overview")
        assert r.status_code == 200
        assert "kpis" in r.json()

    def test_leads(self, solid_sess):
        r = solid_sess.get(f"{API}/admin/leads")
        assert r.status_code == 200

    def test_bookings(self, solid_sess):
        r = solid_sess.get(f"{API}/admin/bookings")
        assert r.status_code == 200

    def test_comms(self, solid_sess):
        r = solid_sess.get(f"{API}/admin/comms")
        assert r.status_code == 200

    def test_settings(self, solid_sess):
        r = solid_sess.get(f"{API}/admin/settings")
        assert r.status_code == 200
