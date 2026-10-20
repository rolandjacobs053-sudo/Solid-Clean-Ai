import asyncio
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

PER_ITEM = {"blinds": {"name": "Blinds cleaning", "price": 8, "unit": "blind", "max_qty": 30},
            "windows": {"name": "Interior windows", "price": 5, "unit": "window", "max_qty": 40},
            "balcony": {"name": "Balcony / patio", "price": 25, "unit": "balcony", "max_qty": 5}}
NEW = [
    {"key": "conservatory", "name": "Conservatory clean", "price": 40, "description": "Floor, frames, sills and interior glass of your conservatory."},
    {"key": "garage", "name": "Garage clean", "price": 35, "description": "Sweep and tidy clean of the garage floor and surfaces."},
    {"key": "garden_furniture", "name": "Garden furniture clean", "price": 20},
    {"key": "wall_washing", "name": "Wall washing", "price": 20, "per_item": True, "unit": "room", "max_qty": 15},
    {"key": "skirting", "name": "Skirting boards & doors deep clean", "price": 10, "per_item": True, "unit": "room", "max_qty": 15},
    {"key": "mattress", "name": "Mattress cleaning", "price": 30, "per_item": True, "unit": "mattress", "max_qty": 10},
    {"key": "sofa", "name": "Sofa / upholstery cleaning", "price": 45, "per_item": True, "unit": "sofa", "max_qty": 6},
    {"key": "rug", "name": "Rug cleaning", "price": 25, "per_item": True, "unit": "rug", "max_qty": 10},
    {"key": "curtains", "name": "Curtain refresh (steam)", "price": 15, "per_item": True, "unit": "pair", "max_qty": 15},
]


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    company = await db.companies.find_one({"slug": "solid-clean"})
    s = await db.settings.find_one({"company_id": str(company["_id"])})
    p = s["pricing"]
    for e in p["extras"]:
        if e["key"] in PER_ITEM:
            e.update(PER_ITEM[e["key"]], per_item=True)
    have = {e["key"] for e in p["extras"]}
    p["extras"] += [e for e in NEW if e["key"] not in have]
    for svc in p["services"]:
        if svc["key"] in ("regular", "end_of_tenancy") and svc.get("extras"):
            svc["extras"] += [e["key"] for e in NEW if e["key"] not in svc["extras"]]
    await db.settings.update_one({"_id": s["_id"]}, {"$set": {"pricing.extras": p["extras"], "pricing.services": p["services"]}})
    print("extras updated", len(p["extras"]))


asyncio.run(main())
