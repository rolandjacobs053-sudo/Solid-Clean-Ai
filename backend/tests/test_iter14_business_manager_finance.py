# Iteration 14: AI Business Manager (chats SSE, stop, memory, priorities, voice) + Finance (expenses, job costs) - owner only
import json
import os
import time

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
OWNER = {"email": "admin@solidcleanltd.com", "password": "SolidClean#2026"}
STAFF = {"email": "test_iter14_staff@example.com", "password": "TEST_staff#2026", "name": "TEST_ Staff"}

MGR = [("get", "/api/admin/manager/chats"), ("post", "/api/admin/manager/chats"), ("get", "/api/admin/manager/memory"),
       ("get", "/api/admin/manager/priorities"), ("post", "/api/admin/manager/priorities/generate"), ("get", "/api/admin/manager/snapshot"),
       ("post", "/api/admin/manager/speak"), ("post", "/api/admin/manager/transcribe"),
       ("get", "/api/admin/finance/summary"), ("get", "/api/admin/finance/expenses"), ("post", "/api/admin/finance/expenses"),
       ("get", "/api/admin/finance/jobs")]


def login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": creds["email"], "password": creds["password"]})
    assert r.status_code == 200, r.text
    return s


def read_sse(resp, stop_after=None):
    events, buf = [], ""
    for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
        buf += chunk
        while "\n\n" in buf:
            part, buf = buf.split("\n\n", 1)
            if part.startswith("data: "):
                events.append(json.loads(part[6:]))
                if stop_after and len([e for e in events if e["type"] == "delta"]) >= stop_after:
                    return events
    return events


@pytest.fixture(scope="module")
def owner():
    return login(OWNER)


@pytest.fixture(scope="module")
def created():
    return {"chats": [], "memory": [], "expenses": []}


def _db():
    return MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


@pytest.fixture(scope="module", autouse=True)
def cleanup(created):
    yield
    s = login(OWNER)
    for c in created["chats"]:
        s.delete(f"{BASE_URL}/api/admin/manager/chats/{c}")
    for m in created["memory"]:
        s.delete(f"{BASE_URL}/api/admin/manager/memory/{m}")
    for e in created["expenses"]:
        s.delete(f"{BASE_URL}/api/admin/finance/expenses/{e}")
    d = _db()
    d.users.delete_many({"email": STAFF["email"]})
    d.priorities.delete_many({})  # no priorities existed before this suite (no delete API)
    d.manager_memory.delete_many({"text": {"$regex": "^TEST_|10,000 monthly profit by December 2027"}})


# Auth: owner-only
class TestOwnerOnly:
    @pytest.mark.parametrize("method,path", MGR)
    def test_401_without_login(self, method, path):
        r = getattr(requests, method)(f"{BASE_URL}{path}", json={})
        assert r.status_code == 401, f"{path} -> {r.status_code}"

    def test_403_for_staff(self, owner):
        r = owner.post(f"{BASE_URL}/api/admin/staff", json={"name": STAFF["name"], "email": STAFF["email"], "password": STAFF["password"]})
        assert r.status_code in (200, 409), r.text
        s = login(STAFF)
        bad = []
        for method, path in MGR:
            rr = getattr(s, method)(f"{BASE_URL}{path}", json={})
            if rr.status_code != 403:
                bad.append((path, rr.status_code))
        assert not bad, bad


# Chat CRUD + SSE
class TestChat:
    def test_chat_stream_title_context(self, owner, created):
        cid = owner.post(f"{BASE_URL}/api/admin/manager/chats", json={}).json()["id"]
        created["chats"].append(cid)
        r = owner.post(f"{BASE_URL}/api/admin/manager/chats/{cid}/messages", json={"text": "TEST_ What was my profit this month? Short answer.", "via": "text"}, stream=True, timeout=120)
        assert r.status_code == 200
        ev = read_sse(r)
        types = [e["type"] for e in ev]
        assert "delta" in types and types[-1] == "done", types
        ans = ev[-1]["text"]
        print("ANSWER1:", ans[:600])
        chat = owner.get(f"{BASE_URL}/api/admin/manager/chats/{cid}").json()
        assert chat["title"].startswith("TEST_ What was my profit")
        assert [m["role"] for m in chat["messages"]] == ["user", "assistant"]
        assert "_id" not in chat
        # follow-up keeps context
        r = owner.post(f"{BASE_URL}/api/admin/manager/chats/{cid}/messages", json={"text": "TEST_ and what about last month? one sentence", "via": "text"}, stream=True, timeout=120)
        ev = read_sse(r)
        print("ANSWER2:", ev[-1]["text"][:600])
        assert ev[-1]["type"] == "done"
        assert "profit" in ev[-1]["text"].lower() or "£0" in ev[-1]["text"]
        # search
        lst = owner.get(f"{BASE_URL}/api/admin/manager/chats", params={"q": "what about last month"}).json()
        assert any(c["id"] == cid for c in lst)
        lst = owner.get(f"{BASE_URL}/api/admin/manager/chats", params={"q": "zzz_nonexistent_TEST_"}).json()
        assert lst == []

    def test_stop_saves_partial(self, owner, created):
        cid = owner.post(f"{BASE_URL}/api/admin/manager/chats", json={}).json()["id"]
        created["chats"].append(cid)
        r = owner.post(f"{BASE_URL}/api/admin/manager/chats/{cid}/messages",
                       json={"text": "TEST_ Write a very long detailed 1500 word marketing plan for my business.", "via": "text"}, stream=True, timeout=120)
        read_sse(r, stop_after=5)
        r.close()
        time.sleep(4)
        chat = owner.get(f"{BASE_URL}/api/admin/manager/chats/{cid}").json()
        assert len(chat["messages"]) == 2, chat["messages"]
        assert chat["messages"][1].get("stopped") is True
        assert len(chat["messages"][1]["text"]) > 0

    def test_memory_suggestion(self, owner, created):
        cid = owner.post(f"{BASE_URL}/api/admin/manager/chats", json={}).json()["id"]
        created["chats"].append(cid)
        r = owner.post(f"{BASE_URL}/api/admin/manager/chats/{cid}/messages", json={"text": "TEST_ Please remember: our target is £10,000 monthly profit by December 2027.", "via": "text"}, stream=True, timeout=120)
        ev = read_sse(r)
        sugg = [e for e in ev if e["type"] == "memory_suggestion"]
        print("SUGG:", sugg)
        assert sugg, "no memory_suggestion event"
        assert "<<REMEMBER" not in ev[-1]["text"]
        msg = owner.get(f"{BASE_URL}/api/admin/manager/chats/{cid}").json()["messages"][1]
        assert msg.get("suggestions") and msg["suggestions"][0]["text"] == sugg[0]["text"], msg
        assert "<<REMEMBER" not in msg["text"]

    def test_delete_chat_404(self, owner):
        cid = owner.post(f"{BASE_URL}/api/admin/manager/chats", json={}).json()["id"]
        assert owner.delete(f"{BASE_URL}/api/admin/manager/chats/{cid}").status_code == 200
        assert owner.get(f"{BASE_URL}/api/admin/manager/chats/{cid}").status_code == 404
        assert owner.delete(f"{BASE_URL}/api/admin/manager/chats/{cid}").status_code == 404

    def test_message_validation(self, owner, created):
        cid = owner.post(f"{BASE_URL}/api/admin/manager/chats", json={}).json()["id"]
        created["chats"].append(cid)
        assert owner.post(f"{BASE_URL}/api/admin/manager/chats/{cid}/messages", json={"text": ""}).status_code == 422
        assert owner.post(f"{BASE_URL}/api/admin/manager/chats/{cid}/messages", json={"text": "x", "via": "fax"}).status_code == 422


# Memory CRUD
class TestMemory:
    def test_memory_crud(self, owner, created):
        r = owner.post(f"{BASE_URL}/api/admin/manager/memory", json={"kind": "target", "text": "TEST_ memory item"})
        mid = r.json()["id"]
        created["memory"].append(mid)
        # dedupe identical text
        r2 = owner.post(f"{BASE_URL}/api/admin/manager/memory", json={"kind": "fact", "text": "TEST_ memory item"})
        assert r2.json()["id"] == mid and r2.json().get("existing") is True
        assert len([i for i in owner.get(f"{BASE_URL}/api/admin/manager/memory").json() if i["text"] == "TEST_ memory item"]) == 1
        items = owner.get(f"{BASE_URL}/api/admin/manager/memory").json()
        assert any(i["id"] == mid and i["kind"] == "fact" for i in items)
        assert owner.put(f"{BASE_URL}/api/admin/manager/memory/{mid}", json={"kind": "bogus", "text": "TEST_ edited"}).status_code == 200
        it = [i for i in owner.get(f"{BASE_URL}/api/admin/manager/memory").json() if i["id"] == mid][0]
        assert it["text"] == "TEST_ edited" and it["kind"] == "fact"
        assert owner.delete(f"{BASE_URL}/api/admin/manager/memory/{mid}").status_code == 200
        assert not any(i["id"] == mid for i in owner.get(f"{BASE_URL}/api/admin/manager/memory").json())
        assert owner.put(f"{BASE_URL}/api/admin/manager/memory/{mid}", json={"kind": "fact", "text": "TEST_ x"}).status_code == 404
        assert owner.delete(f"{BASE_URL}/api/admin/manager/memory/{mid}").status_code == 404
        assert owner.delete(f"{BASE_URL}/api/admin/manager/memory/not-an-id").status_code in (400, 404)


# Voice
class TestVoice:
    def test_tts_stt_roundtrip(self, owner):
        phrase = "How many end of tenancy cleans did we book this month?"
        r = owner.post(f"{BASE_URL}/api/admin/manager/speak", json={"text": phrase}, timeout=60)
        assert r.status_code == 200 and r.headers["content-type"].startswith("audio/mpeg")
        assert len(r.content) > 5000
        with open("/tmp/iter14_tts.mp3", "wb") as f:
            f.write(r.content)
        t = owner.post(f"{BASE_URL}/api/admin/manager/transcribe", files={"file": ("speech.mp3", r.content, "audio/mpeg")}, timeout=60)
        print("STT:", t.status_code, t.text)
        assert t.status_code == 200
        txt = t.json()["text"].lower()
        assert "end of tenancy" in txt and "this month" in txt

    def test_transcribe_too_short(self, owner):
        r = owner.post(f"{BASE_URL}/api/admin/manager/transcribe", files={"file": ("speech.webm", b"x" * 100, "audio/webm")})
        assert r.status_code == 400

    def test_speak_markdown_only_empty(self, owner):
        assert owner.post(f"{BASE_URL}/api/admin/manager/speak", json={"text": "***"}).status_code == 400


# Finance
class TestFinance:
    def test_expense_kpis(self, owner, created):
        ym = time.strftime("%Y-%m")
        before = owner.get(f"{BASE_URL}/api/admin/finance/summary", params={"month": ym}).json()["metrics"]
        r = owner.post(f"{BASE_URL}/api/admin/finance/expenses", json={"date": f"{ym}-02", "category": "supplies", "amount": 12.5, "description": "TEST_ api expense"})
        assert r.status_code == 200
        eid = r.json()["id"]
        created["expenses"].append(eid)
        after = owner.get(f"{BASE_URL}/api/admin/finance/summary", params={"month": ym}).json()["metrics"]
        assert round(after["expenses_recorded"] - before["expenses_recorded"], 2) == 12.5
        assert round(before["profit"] - after["profit"], 2) == 12.5
        assert any(e["id"] == eid for e in owner.get(f"{BASE_URL}/api/admin/finance/expenses", params={"month": ym}).json())
        assert owner.delete(f"{BASE_URL}/api/admin/finance/expenses/{eid}").status_code == 200
        assert owner.delete(f"{BASE_URL}/api/admin/finance/expenses/{eid}").status_code == 404

    def test_expense_validation(self, owner):
        assert owner.post(f"{BASE_URL}/api/admin/finance/expenses", json={"date": "2026-01-02", "category": "nope", "amount": 1}).status_code == 400
        assert owner.post(f"{BASE_URL}/api/admin/finance/expenses", json={"date": "2026-01-02", "category": "supplies", "amount": 0}).status_code == 422
        assert owner.post(f"{BASE_URL}/api/admin/finance/expenses", json={"date": "02/01/2026", "category": "supplies", "amount": 1}).status_code == 422

    def test_jobs_and_demo_excluded(self, owner):
        ym = time.strftime("%Y-%m")
        jobs = owner.get(f"{BASE_URL}/api/admin/finance/jobs", params={"month": ym}).json()
        m = owner.get(f"{BASE_URL}/api/admin/finance/summary", params={"month": ym}).json()["metrics"]
        live = [j for j in jobs if not j["demo"]]
        print("jobs:", len(jobs), "live:", len(live), "metrics revenue:", m["revenue"])
        assert m["jobs_booked_or_done"] == len(live)
        assert m["revenue"] == round(sum(float(j["total"] or 0) for j in live), 2)

    def test_job_costs_on_demo_job(self, owner):
        ym = time.strftime("%Y-%m")
        jobs = [j for j in owner.get(f"{BASE_URL}/api/admin/finance/jobs", params={"month": ym}).json() if j["demo"]]
        if not jobs:
            pytest.skip("no demo job this month")
        j = jobs[0]
        prev = j["job_costs"]
        rev_before = owner.get(f"{BASE_URL}/api/admin/finance/summary", params={"month": ym}).json()["metrics"]
        r = owner.put(f"{BASE_URL}/api/admin/finance/jobs/{j['id']}/costs", json={"cleaner_pay": 40, "supplies": 5, "travel": 3.5})
        assert r.status_code == 200
        j2 = [x for x in owner.get(f"{BASE_URL}/api/admin/finance/jobs", params={"month": ym}).json() if x["id"] == j["id"]][0]
        assert j2["cost_total"] == 48.5
        rev_after = owner.get(f"{BASE_URL}/api/admin/finance/summary", params={"month": ym}).json()["metrics"]
        assert rev_after["job_costs_recorded"] == rev_before["job_costs_recorded"], "demo job cost leaked into KPI"
        # reset: restore original state (remove field if it was absent)
        if prev is None:
            from bson import ObjectId
            _db().bookings.update_one({"_id": ObjectId(j["id"])}, {"$unset": {"job_costs": ""}})
        else:
            owner.put(f"{BASE_URL}/api/admin/finance/jobs/{j['id']}/costs", json={k: prev.get(k, 0) for k in ("cleaner_pay", "supplies", "travel")})
        assert owner.put(f"{BASE_URL}/api/admin/finance/jobs/000000000000000000000000/costs", json={}).status_code == 404


# Priorities: generate (real LLM), approve/dismiss/complete, plan checklist, checklist toggle
class TestPriorities:
    def test_priorities_flow(self, owner):
        r = owner.post(f"{BASE_URL}/api/admin/manager/priorities/generate", timeout=180)
        assert r.status_code == 200, r.text
        items = [p for p in r.json() if p["status"] == "suggested"]
        print("PRIORITIES:", [(p["title"], p["priority"], p["cost"]) for p in items])
        assert 1 <= len(items) <= 3
        assert all(p["priority"] in ("high", "medium", "low") and p["title"] for p in items)
        pid = items[0]["id"]
        assert owner.patch(f"{BASE_URL}/api/admin/manager/priorities/{pid}", json={"status": "approved"}).json()["status"] == "approved"
        if len(items) > 1:
            assert owner.patch(f"{BASE_URL}/api/admin/manager/priorities/{items[1]['id']}", json={"status": "dismissed"}).json()["status"] == "dismissed"
        p = owner.post(f"{BASE_URL}/api/admin/manager/priorities/{pid}/plan", timeout=180)
        assert p.status_code == 200, p.text
        cl = p.json()["checklist"]
        print("CHECKLIST:", cl)
        assert 1 <= len(cl) <= 8 and all(c["done"] is False for c in cl)
        cl[0]["done"] = True
        owner.patch(f"{BASE_URL}/api/admin/manager/priorities/{pid}", json={"checklist": cl})
        got = [x for x in owner.get(f"{BASE_URL}/api/admin/manager/priorities").json() if x["id"] == pid][0]
        assert got["checklist"][0]["done"] is True and got["checklist"][1]["done"] is False
        assert owner.patch(f"{BASE_URL}/api/admin/manager/priorities/{pid}", json={"status": "completed"}).json()["status"] == "completed"
        assert owner.patch(f"{BASE_URL}/api/admin/manager/priorities/000000000000000000000000", json={"status": "approved"}).status_code == 404
        assert owner.patch(f"{BASE_URL}/api/admin/manager/priorities/{pid}", json={"status": "bogus"}).status_code == 422
