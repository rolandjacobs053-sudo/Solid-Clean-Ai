"""Iteration 12 UI cleanup: cancels the real weekly booking via the admin API (verifies plan cascade), then deletes all test_res12 data."""
import os

import requests
import stripe
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

E = dotenv_values("/app/backend/.env")
db = MongoClient(E["MONGO_URL"])[E["DB_NAME"]]
stripe.api_key = E["STRIPE_SECRET_KEY"]
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
s = requests.Session()
s.post(f"{BASE}/api/auth/login", json={"email": "admin@solidcleanltd.com", "password": "SolidClean#2026"}, timeout=20)
bs = list(db.bookings.find({"customer.email": {"$regex": "^test_res12_"}}))
for b in bs:
    if b.get("recurring_plan_id") and b["status"] == "confirmed":
        r = s.patch(f"{BASE}/api/admin/bookings/{b['_id']}", json={"status": "cancelled"}, timeout=20)
        p = db.recurring_plans.find_one({"_id": ObjectId(b["recurring_plan_id"])})
        print("cancel", r.status_code, "plan status after cancel:", p and p["status"])
plan_ids = [b["recurring_plan_id"] for b in bs if b.get("recurring_plan_id")]
child = [c["_id"] for c in db.bookings.find({"recurring_plan_id": {"$in": plan_ids}})]
ids = [b["_id"] for b in bs] + child
db.payment_transactions.delete_many({"booking_id": {"$in": [str(i) for i in ids]}})
db.bookings.delete_many({"_id": {"$in": ids}})
db.recurring_plans.delete_many({"_id": {"$in": [ObjectId(p) for p in plan_ids]}})
leads = [l["_id"] for l in db.leads.find({"email": {"$regex": "^test_res12_"}})] + [ObjectId(b["lead_id"]) for b in bs if b.get("lead_id")]
db.quotes.delete_many({"lead_id": {"$in": [str(l) for l in leads]}})
db.communications.delete_many({"$or": [{"to": {"$regex": "^test_res12_"}}, {"lead_id": {"$in": [str(l) for l in leads]}}]})
db.leads.delete_many({"_id": {"$in": leads}})
for b in bs:
    if b.get("session_id"):
        try:
            sess = stripe.checkout.Session.retrieve(b["session_id"])
            if sess.customer:
                stripe.Customer.delete(sess.customer)
        except Exception:
            pass
print("left:", db.bookings.count_documents({"customer.name": {"$regex": "^TEST_"}}), db.recurring_plans.count_documents({"customer.name": {"$regex": "^TEST_"}}),
      db.leads.count_documents({"name": {"$regex": "^TEST_"}}), db.communications.count_documents({"to": {"$regex": "^test_res1"}}))
st = db.settings.find_one({"company_id": "6acb2a20e5d23531c955e49b"})["pricing"]
print("blinds", next(e for e in st["extras"] if e["key"] == "blinds")["price"], "weekly", next(f for f in st["residential"]["frequencies"] if f["key"] == "weekly")["discount"], "extras", len(st["extras"]))
