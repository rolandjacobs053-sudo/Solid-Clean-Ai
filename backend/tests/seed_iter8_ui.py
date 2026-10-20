"""Seed / cleanup TEST_ bookings for iteration 8 UI tests. Usage: python seed_iter8_ui.py seed|clean"""
import datetime as dt
import json
import sys
import uuid
from zoneinfo import ZoneInfo

from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

ENV = dotenv_values("/app/backend/.env")
DB = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
CID = "6acb2a20e5d23531c955e49b"


def seed():
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    lid = str(DB.leads.insert_one({"company_id": CID, "name": "TEST_ UI Lead", "email": "delivered@resend.dev", "phone": "07700900111",
                                   "status": "booked", "source": "website", "timeline": [], "created_at": now}).inserted_id)
    out = {"lead": lid}
    today = dt.datetime.now(ZoneInfo("Europe/London")).date()
    for key, days, status, pay, tip in (("d10", 10, "confirmed", "paid", 5), ("d4", 4, "confirmed", "paid", 0), ("d1", 1, "confirmed", "paid", 0),
                                        ("due", 6, "confirmed", "due", 0), ("done", -1, "completed", "paid", 8)):
        doc = {"company_id": CID, "lead_id": lid, "quote_id": str(ObjectId()), "customer": {"name": f"TEST_ Ui{key} Customer", "email": "delivered@resend.dev",
               "phone": "07700900111"}, "postcode": "SW1A 1AA", "address": "TEST_ 1 UI Street", "service": "regular", "service_name": "Residential / Regular Clean",
               "total": 120.0, "deposit_amount": 120.0, "balance_due": 0, "tip": tip, "date": (today + dt.timedelta(days=days)).isoformat(), "slot": "08:00",
               "status": status, "payment_status": pay, "reference": f"TS-{uuid.uuid4().hex[:6].upper()}", "source": "website", "created_at": now,
               "lines": [{"label": "Regular clean", "amount": 120.0}]}
        out[key] = str(DB.bookings.insert_one(doc).inserted_id)
    print(json.dumps(out))


def clean():
    bids = [b["_id"] for b in DB.bookings.find({"customer.name": {"$regex": "^TEST_"}}, {"_id": 1})]
    lids = {b.get("lead_id") for b in DB.bookings.find({"_id": {"$in": bids}}, {"lead_id": 1})}
    lids |= {str(l["_id"]) for l in DB.leads.find({"name": {"$regex": "^TEST_"}}, {"_id": 1})}
    lids.discard(None)
    r = [DB.payment_transactions.delete_many({"booking_id": {"$in": [str(b) for b in bids]}}).deleted_count,
         DB.bookings.delete_many({"_id": {"$in": bids}}).deleted_count,
         DB.communications.delete_many({"lead_id": {"$in": list(lids)}}).deleted_count,
         DB.quotes.delete_many({"lead_id": {"$in": list(lids)}}).deleted_count,
         DB.leads.delete_many({"_id": {"$in": [ObjectId(l) for l in lids]}}).deleted_count]
    print("deleted tx/bookings/comms/quotes/leads", r)


if __name__ == "__main__":
    seed() if sys.argv[1] == "seed" else clean()
