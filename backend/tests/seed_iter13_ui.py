"""Seed TEST_ data for iteration 13 UI tests. Run with `cleanup` arg to delete everything tagged ui13."""
import datetime as dt
import json
import os
import sys

import requests
from dotenv import dotenv_values
from pymongo import MongoClient

ENV = dotenv_values("/app/backend/.env")
DB = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
CID = "6acb2a20e5d23531c955e49b"
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
T = dt.date.today()
TAG = {"ui13": True}

if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
    leads = [str(x["_id"]) for x in DB.leads.find(TAG)]
    bids = [str(x["_id"]) for x in DB.bookings.find(TAG)]
    print(DB.reviews.delete_many({"booking_id": {"$in": bids}}).deleted_count, "reviews")
    print(DB.communications.delete_many({"lead_id": {"$in": leads}}).deleted_count, "comms")
    for c in ("bookings", "recurring_plans", "leads"):
        print(DB[c].delete_many(TAG).deleted_count, c)
    sys.exit()


def lead(n):
    return str(DB.leads.insert_one({**TAG, "company_id": CID, "name": n, "email": "test_ui13@example.com", "status": "booked", "timeline": []}).inserted_id)


out = {"plans": {}}
for key, freq, total, status, card in [("weekly", "weekly", 60.0, "active", True), ("fortnightly", "fortnightly", 80.0, "active", True),
                                        ("monthly", "monthly", 100.0, "paused", True), ("cancelled", "weekly", 40.0, "cancelled", True)]:
    doc = {**TAG, "company_id": CID, "lead_id": lead(f"TEST_UI {key}"), "customer": {"name": f"TEST_UI {key.title()}", "email": "test_ui13@example.com", "phone": "07700900123"},
           "postcode": "SW11 5RT", "service": "regular", "service_name": "Residential / Regular Clean", "total": total, "frequency": freq,
           "next_date": (T + dt.timedelta(days=4)).isoformat(), "slot": "09:00", "status": status, "last_result": None, "anchor_day": 1,
           "payment_method": "pm_TEST" if card else None, "created_at": dt.datetime.utcnow().isoformat()}
    out["plans"][key] = str(DB.recurring_plans.insert_one(doc).inserted_id)

lid = lead("TEST_UI Feedback")
bid = str(DB.bookings.insert_one({**TAG, "company_id": CID, "lead_id": lid, "customer": {"name": "TEST_UI Feedback Person", "email": "test_ui13@example.com", "phone": "07700900123"},
                                  "postcode": "SW11 5RT", "service": "regular", "service_name": "Residential / Regular Clean", "input": {}, "total": 60.0,
                                  "date": T.isoformat(), "slot": "10:00", "status": "confirmed", "payment_status": "paid", "source": "website"}).inserted_id)
s = requests.Session()
s.post(f"{BASE}/api/auth/login", json={"email": "admin@solidcleanltd.com", "password": "SolidClean#2026"}, timeout=20)
r = s.patch(f"{BASE}/api/admin/bookings/{bid}", json={"status": "completed"}, timeout=30)
c = DB.communications.find_one({"lead_id": lid, "template": "feedback_review_request"})
out.update(booking=bid, complete_status=r.status_code, link=c["link"][1] if c else None)
print(json.dumps(out))
