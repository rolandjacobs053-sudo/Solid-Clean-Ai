import asyncio
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

from pricing import RESIDENTIAL  # noqa: E402


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    company = await db.companies.find_one({"slug": "solid-clean"})
    res = await db.settings.update_one({"company_id": str(company["_id"]), "pricing.residential": {"$exists": False}}, {"$set": {"pricing.residential": RESIDENTIAL}})
    print("residential pricing added" if res.modified_count else "already present")


asyncio.run(main())
