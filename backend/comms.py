from core import company_name, get_settings, now_iso, tdb
from mailer import VALID_EMAIL, render_html, send_email


async def is_suppressed(email: str) -> bool:
    return bool(email) and bool(await tdb.suppressions.find_one({"email": email.lower().strip()}))


async def deliver_email(to: str, subject: str, body: str, link=None) -> str:
    if not to or not VALID_EMAIL.match(to.strip()):
        return "no_address"
    s = await get_settings()
    reply_to = next((e for e in (s["business"].get("contact_email"), s["business"].get("email")) if e and VALID_EMAIL.match(e)), "")
    return await send_email(to=to.strip(), subject=subject, html=render_html(company_name(), body, link), from_name=company_name(), reply_to=reply_to)


async def log_comm(to: str, channel: str, template: str, subject: str, body: str,
                   kind: str = "transactional", lead_id=None, scheduled_for=None, extra=None, link=None):
    status = "simulated"
    if kind in ("marketing", "follow_up") and await is_suppressed(to):
        status = "blocked_opt_out"
    elif scheduled_for:
        status = "scheduled"
    elif channel == "email" and kind != "marketing":
        status = await deliver_email(to, subject, body, link)
    doc = {"to": to, "channel": channel, "template": template, "subject": subject, "body": body,
           "kind": kind, "status": status, "lead_id": lead_id, "scheduled_for": scheduled_for,
           "link": list(link) if link else None, "created_at": now_iso(), **(extra or {})}
    if status in ("sent", "failed", "paused"):
        doc["sent_at"] = now_iso()
    await tdb.communications.insert_one(doc)
    return status


async def add_event(lead_id, kind: str, text: str):
    if lead_id:
        from core import oid
        await tdb.leads.update_one({"_id": oid(str(lead_id))}, {
            "$push": {"timeline": {"at": now_iso(), "type": kind, "text": text}},
            "$set": {"updated_at": now_iso()}})


async def upsert_lead(contact: dict, source: str, event_text: str, extra=None) -> str:
    email = (contact.get("email") or "").lower().strip()
    phone = (contact.get("phone") or "").replace(" ", "")
    query = [q for q in ({"email": email} if email else None, {"phone": phone} if phone else None) if q]
    existing = await tdb.leads.find_one({"$or": query}) if query else None
    fields = {k: v for k, v in {"name": contact.get("name"), "email": email or None, "phone": phone or None,
                                "postcode": contact.get("postcode")}.items() if v}
    fields.update(extra or {})
    if existing:
        await tdb.leads.update_one({"_id": existing["_id"]}, {"$set": {**fields, "updated_at": now_iso()}})
        lead_id = str(existing["_id"])
    else:
        doc = {"name": "Unknown", "status": "new", "source": source, "type": "residential", "notes": "",
               "follow_up_date": None, "timeline": [], "marketing_consent": False,
               "created_at": now_iso(), "updated_at": now_iso(), **fields}
        lead_id = str((await tdb.leads.insert_one(doc)).inserted_id)
    await add_event(lead_id, source, event_text)
    return lead_id


def quote_email(name: str, quote: dict) -> str:
    lines = "\n".join(f"  - {l['label']}: £{l['amount']:.2f}" for l in quote["lines"])
    return (f"Hi {name},\n\nThank you for your enquiry with {company_name()}. Here is your quotation for "
            f"{quote['service_name']}:\n{lines}\n  Total: £{quote['total']:.2f}\n\n"
            f"Use the button below to choose an available date and time and pay securely to confirm.\n\nKind regards,\n{company_name()}")


def booking_link(request, slug: str, quote_id: str) -> tuple:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    return ("View quote & book", f"https://{host}/c/{slug}/quote?q={quote_id}")
