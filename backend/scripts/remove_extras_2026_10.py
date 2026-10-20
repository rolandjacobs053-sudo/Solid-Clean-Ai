import asyncio
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

REMOVE = {"garden_furniture", "wall_washing", "mattress", "sofa", "rug", "curtains"}


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    company = await db.companies.find_one({"slug": "solid-clean"})
    s = await db.settings.find_one({"company_id": str(company["_id"])})
    p = s["pricing"]
    extras = [e for e in p["extras"] if e["key"] not in REMOVE]
    for svc in p["services"]:
        if svc.get("extras"):
            svc["extras"] = [k for k in svc["extras"] if k not in REMOVE]
    await db.settings.update_one({"_id": s["_id"]}, {"$set": {"pricing.extras": extras, "pricing.services": p["services"]}})
    print("removed", len(p["extras"]) - len(extras), "extras; remaining", [e["name"] for e in extras])


asyncio.run(main())
