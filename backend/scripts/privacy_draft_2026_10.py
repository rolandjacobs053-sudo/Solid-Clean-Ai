import asyncio
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

TEXT = """Solid Clean Ltd ("we", "us") is the data controller for the personal information collected through this website, our booking and enquiry forms, our AI assistant and by telephone. Contact: info@solidcleanltd.com, 020 3728 4419. [REVIEW REQUIRED: registered office address and ICO registration number]

What we collect
- Your name, email address and telephone number.
- The property or premises address and postcode, property details (for example rooms, condition, furnishing, pets) and cleaning requirements.
- Access and key-collection instructions you give us (for example estate agency details or the person giving access).
- Photographs you upload of your property or premises, and before/after photographs our team takes of the work.
- Booking, appointment, payment status and communication history. Card payments are processed by Stripe; we never see or store your full card number.
- Messages you send to our AI assistant or our team.

Why we use it
- To provide quotations, arrange site walkthroughs, take and manage bookings and carry out the cleaning (performance of a contract).
- To send booking confirmations, reminders and service messages.
- To handle complaints, re-cleans and claims, and keep business and accounting records (legal obligation and legitimate interests).
- To send marketing only where you have opted in. You can unsubscribe at any time.

Photographs
Photos you upload are used only to understand the property's condition and plan the work. They are stored privately, linked to your booking or enquiry, and can only be viewed by authorised Solid Clean Ltd staff, including the cleaners assigned to your job. Location data is removed from uploaded photos. Please avoid photographing people or personal documents.

Who we share it with
Our cleaning staff assigned to your job; Stripe (payments); our email, hosting and storage providers; and an AI provider that helps answer enquiries. We do not sell your personal information. [REVIEW REQUIRED: confirm the list of processors and any transfers outside the UK]

How long we keep it
[REVIEW REQUIRED: retention periods - for example booking and accounting records 6 years, photographs X months after the job, unsuccessful enquiries X months]

Your rights
You can ask for access to, correction or deletion of your personal data, object to or restrict its use, or ask for a copy of it, by emailing info@solidcleanltd.com. You can also complain to the Information Commissioner's Office (ico.org.uk)."""


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    company = await db.companies.find_one({"slug": "solid-clean"})
    r = await db.policies.update_one({"company_id": str(company["_id"]), "key": "privacy"},
                                     {"$set": {"draft_content": TEXT, "needs_review": True, "updated_at": datetime.now(timezone.utc).isoformat()}})
    print("privacy draft updated", r.modified_count)


asyncio.run(main())
