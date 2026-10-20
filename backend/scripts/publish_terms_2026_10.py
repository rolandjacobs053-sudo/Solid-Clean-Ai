import asyncio
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

TITLE = "Terms and Conditions"
TERMS = """These Terms and Conditions govern the provision of cleaning services by Solid Clean ("the Company", "we", "us") to our customers ("the Client", "you"). By booking our services, you agree to be bound by these terms. These Terms are governed by the laws of England and Wales.

1. Payment Terms (Full Payment)
- Full payment is required at the time of booking to secure the appointment.
- Payment can be made by card, bank transfer, or as specified during the booking process.
- We reserve the right to amend the quotation if the scope of work changes (e.g., additional rooms, heavier soiling, larger property than described, or additional services).
- All additional charges (parking, congestion charge, rescheduling fees, etc.) must be settled on the day of service.
- Prices are exclusive of VAT where applicable. Late payments may incur interest and recovery costs.

2. Cancellations, Rescheduling & Company Cancellation Policy

Customer Cancellations & Rescheduling:
- Cancellations with 7+ days' notice: Eligible for a full refund.
- Cancellations between 48 hours and 7 days' notice: Eligible for a 50% refund.
- Cancellations with less than 48 hours' notice (including 24 hours or less): Nonrefundable, as insufficient notice prevents the appointment slot from being filled. No shows or cancellation on arrival are treated as late cancellations and result in the full fee being payable with no refund.
- Rescheduling: One free reschedule is permitted if requested with at least 48 hours' notice. Requests with less than 48 hours' notice are treated as a late cancellation and are non-refundable.

Company Cancellation:
- We may cancel or reschedule due to unforeseen circumstances (e.g., staff illness, extreme weather, or access issues) with as much notice as possible. We will offer an alternative date or full refund where appropriate.
- No liability for losses arising from such cancellations beyond refunding payments made.

3. 15-Minute Waiting Policy
- Our teams aim to arrive at the agreed time. If you (or your representative) are not present to provide access within 15 minutes of the scheduled start, we may treat this as a no-access situation.
- In such cases, the full fee is payable with no refund, and the service may be rescheduled (subject to availability and possible additional charges).

4. Parking policy and cancellation fees
- Client Responsibility: It is the Client's strict responsibility to arrange and guarantee suitable, legal parking for at least one service vehicle within reasonable proximity to the property for the full duration of the clean. Detailed parking instructions, including resident permits, visitor passes, or designated private spaces, must be provided prior to arrival.
- Congestion Charges and Travel Expenses: The Client is fully liable for all vehicle travel expenses incurred to fulfill the booking, including Congestion Charges and Low Emission Zone fees. These charges will be billed or deducted at exact cost (£18.00 daily pass rate), plus a £10.00 administration fee for payment handling.
- Failure to Provide Parking: Our teams are strictly prohibited from parking illegally, blocking access, or risking Penalty Charge Notices (PCNs). If suitable and legal parking cannot be accessed within 20 minutes of arrival, we reserve the right to cancel the service. Because our operatives are booked exclusively for your slot, cannot be reassigned on short notice, and must still be paid for their time and travel, 100% of the booking fee will be retained as liquidated damages to cover staff wages, lost daily schedule capacity, and administrative costs.
- Fines and Penalties: The Client is 100% liable for any parking fines, PCNs, or towing fees resulting from invalid permits or incorrect instructions provided by the Client. A £20.00 administration fee will apply to process any associated notices.

5. Access and Key Collection Policy
- You must ensure safe and timely access to the property, including providing keys, codes, or instructions.
- Key collection/return from third parties (e.g., estate agents) may incur an additional fee if outside the local area.
- Keys must open all required locks without special tools. We are not responsible for lost keys beyond reasonable care.
- If access cannot be gained through no fault of ours, full payment is retained (no refund).

6. Customer Behaviour and Zero-Tolerance Policy
- We expect courteous and respectful behavior towards our staff. Verbal abuse, harassment, discrimination, or threatening conduct will not be tolerated.
- In such cases, we reserve the right to immediately terminate the service, retain full payment, and refuse future bookings. We may also report incidents to the police where appropriate.

7. Staff Safety Policy
- The property must be safe for our staff (no hazardous materials, aggressive pets, structural dangers, etc.).
- You must provide running hot water, electricity, and adequate lighting.
- We reserve the right to suspend or cancel services if the environment poses a risk to staff health and safety, with full payment retained (no refund).

8. End of Tenancy Cleaning Terms
- Our end-of-tenancy cleans aim to return the property to a professional standard (as at check-in, allowing for fair wear and tear).
- This is charged based on property size, number of rooms, and condition. A detailed quote is provided.
- Note: Under the Tenant Fees Act 2019, landlords cannot require tenants to use or pay for professional cleaning in new agreements, but tenants/landlords may still book voluntarily.

9. Carpet, Oven and Appliance Cleaning Terms
- These are specialist add-ons and must be requested and paid for separately.
- Ovens/fridges must be emptied, defrosted, and switched off beforehand. Carpets should be cleared of large debris.
- Results depend on the original condition; we cannot guarantee removal of all old stains, burns, or embedded dirt.

10. Damage and Liability
- We are not liable for pre-existing damage, stains, or issues that cannot be fully resolved with standard methods.
- We accept liability only for direct damage caused by our negligence (up to the value of the service or as limited by insurance).
- You must secure valuables and fragile items. We are not responsible for loss or breakage of unsecured items.
- Claims must be notified immediately in writing.

11. Satisfaction Guarantee
- We offer a satisfaction guarantee (typically 24-48 hours). Notify us in writing within this period of any issues.
- We will arrange a re-clean of the affected areas at no extra cost where possible.
- The guarantee does not apply if the property is re-occupied, altered, or if access for reclean is not provided. It excludes areas not included in the original booking.

12. Refund Policy
- Refunds are issued strictly in accordance with our tiered cancellation schedule outlined in Section 2 (full refund for 7+ days' notice, 50% refund for 48 hours to 7 days' notice, and non-refundable for less than 48 hours' notice).
- No refunds are provided for late cancellations, no-shows, or after service completion (except at our sole discretion for valid guarantee claims, usually offered as a re-clean rather than cash refund).

13. Chargeback and Payment Dispute Policy
- Unwarranted chargebacks or disputes will be vigorously defended. You agree to reimburse us for any costs incurred (including legal and bank fees).
- All disputes must first go through our complaints procedure.

14. Force Majeure
- We are not liable for failure or delay in performance due to events beyond our reasonable control (e.g., severe weather, pandemics, strikes, power failures, or government restrictions).
- In such cases, we will notify you and seek to reschedule or provide a full refund where appropriate.

15. Complaints Procedure
- Raise any issues immediately on the day where possible, and in writing (email) within 48 hours.
- We will investigate promptly and offer a resolution (e.g., re-clean).
- If unresolved, you may contact us for escalation. Persistent failure to allow re-clean voids the guarantee.

16. Privacy and GDPR
- We collect and process your personal data (contact details, property info, payment data) solely for providing the service, as per our Privacy Policy.
- Data is handled in accordance with the UK GDPR and Data Protection Act 2018. You have rights to access, rectification, erasure, etc. Contact us for details.

17. Governing Law
- These Terms are governed by the laws of England and Wales. Any disputes shall be subject to the exclusive jurisdiction of the courts of England and Wales."""

KB = {
    "Can I reschedule or cancel?": "Cancellations with 7+ days' notice are eligible for a full refund, between 48 hours and 7 days' notice for a 50% refund, and with less than 48 hours' notice are non-refundable. One free reschedule is permitted if requested with at least 48 hours' notice. Full details are in our Terms and Conditions.",
    "How do I pay?": "Full payment is required at the time of booking to secure the appointment, paid securely by card through Stripe. Full details are in our Terms and Conditions.",
}


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    company = await db.companies.find_one({"slug": "solid-clean"})
    cid, ts = str(company["_id"]), datetime.now(timezone.utc).isoformat()
    p = await db.policies.find_one({"company_id": cid, "key": "terms"})
    if p.get("published_content") != TERMS:
        v = p["published_version"] + 1
        version = {"version": v, "content": TERMS, "title": TITLE, "effective_date": ts[:10], "published_at": ts, "published_by": "owner-approved (chat 2026-10-20)"}
        await db.policies.update_one({"_id": p["_id"]}, {"$set": {"title": TITLE, "draft_content": TERMS, "published_content": TERMS, "published_version": v,
                                                               "needs_review": False, "require_acceptance": True, "published_at": ts, "effective_date": ts[:10]},
                                                      "$push": {"versions": version}})
        await db.audit_logs.insert_one({"company_id": cid, "action": "policy.publish", "detail": f"terms v{v}", "actor": "owner-approved", "at": ts})
        print("published terms", v)
    s = await db.settings.find_one({"company_id": cid})
    for item in s["knowledge_base"]:
        if item["q"] in KB:
            item["a"] = KB[item["q"]]
    await db.settings.update_one({"_id": s["_id"]}, {"$set": {"knowledge_base": s["knowledge_base"], "business.payment_mode": "full_upfront"}})
    print("faq updated")


asyncio.run(main())
