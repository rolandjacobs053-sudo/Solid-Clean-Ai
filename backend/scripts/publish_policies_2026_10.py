import asyncio
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

COMPANY_POLICY = """At Solid Clean Ltd, we are committed to delivering professional, reliable, and high-quality cleaning services. To ensure clarity and a smooth experience for everyone, we kindly ask all clients to read and agree to the following policy before confirming a booking.

1. Deposit Requirement
A 50% deposit is required to confirm your booking. This guarantees your slot and allows us to allocate the necessary time, personnel, and resources to prepare for your job.

2. Non-Refundable Deposit Policy
All deposits are strictly non-refundable. Once we receive your deposit, we:
- Reserve your time slot exclusively
- Allocate cleaning staff and transportation
- Plan the job in advance
- Decline any other booking requests for that time
These commitments involve real time and costs, even if the booking is later cancelled or rescheduled.

3. Booking Confirmation
Your booking is only confirmed once the deposit is paid through our secure Stripe system. We do not hold or reserve time slots without a deposit.

4. Cancellations & Rescheduling
- You must provide at least 48 hours' notice to reschedule. We will do our best to accommodate your new preferred date.
- Cancellations made with less than 48 hours' notice will result in the deposit being forfeited.
- If Solid Clean Ltd needs to reschedule or cancel, your deposit will be transferred to the new appointment with no additional charges.

5. Payment Methods
We only accept card payments via Stripe. You can pay using:
- A secure Stripe payment link (sent for deposit and/or final balance)
- Or by card directly, using our Stripe terminal or mobile app at the property
Cash payments are not accepted under any circumstances. This ensures safe, traceable, and professional transactions for both parties.

6. Final Payment
The remaining 50% balance is due immediately after the cleaning is completed. We will either:
- Send you an invoice with a Stripe link, or
- Take the payment on-site using our Stripe system
A digital receipt is available upon request.

7. Late Payments
Prompt payment protects your ability to book future services. In the event of delayed payment:
- A £45 late payment fee will be applied
- An additional £5 per day will be charged for each day a payment reminder must be sent
- Continued non-payment may result in debt recovery action and a ban on future bookings

8. Property Access
You must ensure safe and timely access to the property at the agreed time. If we are unable to access the property or are significantly delayed due to lack of access, the deposit will be forfeited, and the full service fee may still be charged.

9. Parking
Please arrange suitable parking for our team and equipment. Any parking charges or penalties caused by lack of access or incorrect instructions will be added to your final invoice.

10. Cleaning Results Disclaimer
We always aim for excellent results, but outcomes depend on:
- The condition of the property
- Age and type of stains
- Material/surface type
- Any pre-existing damage or wear
We cannot guarantee 100% stain or damage removal, but we will always deliver the highest possible standard.

11. Liability
Solid Clean Ltd is fully insured. However, we are not liable for:
- Pre-existing damage
- Loose fixtures or fittings
- Poor maintenance of surfaces, appliances, or materials
All claims or concerns must be reported within 24 hours of the service being completed.

12. Health & Safety
For the safety of our staff and service quality, we reserve the right to refuse service if the property is unsafe or unhygienic due to:
- Aggressive or loose pets
- Hoarding, blocked access, or excessive clutter
- Biohazards or dangerous waste
- Faulty or dangerous electrical setups

13. Acceptance of Terms
By paying your deposit, you confirm that you have read, understood, and accepted this policy in full. Solid Clean Ltd reserves the right to update or amend this policy at any time, with reasonable notice given to all affected clients."""

GUARANTEE = """Is your work guaranteed?
In the unlikely event you are not absolutely satisfied, please contact us within 24h, and we'll re-perform that service free of cost.

Refund policy
Our Cleaning Company does not offer refunds. In the unfortunate event that a client is not happy by a service carried out by our Cleaning Company, the issue must be raised with us within 24hrs of completion of the service. Once we established the claim is reality based, we will rectify the issues at no extra cost to the client within 48hrs.

If there is a problem, who can I call?
Our reputation depends on our exceptional standards which we take very seriously. However in the unlikely event of any concern, please telephone us on 020 3728 4419, or email info@solidcleanltd.com, and we will do our utmost to resolve it immediately.

What if something gets broken?
We are fully insured. If you have any items which are particularly delicate or irreplaceable, or of high sentimental value, please let us know so we can discuss your requirements. As you'd expect, we treat your possessions with the utmost care. In the highly unlikely event that something is damaged or broken, the supervisor will leave notification in writing for you and we will endeavour to contact you immediately.

How will I recognise your staff?
Our staff will be wearing our uniforms Solid Clean.

What about my pets?
We love pets. It would be ideal if you would introduce the team to your pet(s) during the first visit."""

PUBLISH = [("terms", "Solid Clean Ltd - Company Policy (booking terms)", COMPANY_POLICY, True),
           ("complaints", "Service guarantee, refunds & breakages", GUARANTEE, False)]


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    company = await db.companies.find_one({"slug": "solid-clean"})
    cid, ts = str(company["_id"]), datetime.now(timezone.utc).isoformat()
    await db.policies.update_many({"company_id": cid, "published_version": 0}, {"$set": {"require_acceptance": False}})
    for key, title, content, req in PUBLISH:
        p = await db.policies.find_one({"company_id": cid, "key": key})
        if p.get("published_content") == content:
            continue
        v = p["published_version"] + 1
        version = {"version": v, "content": content, "title": title, "effective_date": ts[:10], "published_at": ts, "published_by": "owner-approved (chat 2026-10-20)"}
        await db.policies.update_one({"_id": p["_id"]}, {"$set": {"title": title, "draft_content": content, "published_content": content, "published_version": v,
                                                                   "needs_review": False, "require_acceptance": req, "published_at": ts, "effective_date": ts[:10]},
                                                          "$push": {"versions": version}})
        await db.audit_logs.insert_one({"company_id": cid, "action": "policy.publish", "detail": f"{key} v{v}", "actor": "owner-approved", "at": ts})
        print("published", key, v)


asyncio.run(main())
