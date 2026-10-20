import asyncio
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

CARPET = {"requires_survey": True, "from_price": 100, "min_price": 100,
          "description": "Carpets can harbour allergens, dust and dirt, affecting the overall cleanliness and air quality of your space. Our professional carpet cleaning service is designed to lift deep-seated dirt, stains and allergens, leaving your carpets fresh, soft and revitalised."}
FAQ = {"q": "How much does carpet cleaning cost?",
       "a": "Professional carpet cleaning starts from £100. The final price depends on the number of areas, the size of the carpets, the number of stairs, their condition and any specialist treatment required. Request a carpet cleaning quote on our Carpet Cleaning page and upload photos of your carpets - we'll review them and send you a quote. Your booking is not confirmed until we approve the appointment."}


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    company = await db.companies.find_one({"slug": "solid-clean"})
    s = await db.settings.find_one({"company_id": str(company["_id"])})
    for svc in s["pricing"]["services"]:
        if svc["key"] == "carpet":
            svc.update(CARPET)
    kb = [k for k in s["knowledge_base"] if k["q"] != FAQ["q"]] + [FAQ]
    await db.settings.update_one({"_id": s["_id"]}, {"$set": {"pricing.services": s["pricing"]["services"], "knowledge_base": kb}})
    print("carpet service updated")


asyncio.run(main())
