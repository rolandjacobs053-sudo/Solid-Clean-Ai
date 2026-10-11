from core import company_name, now_iso, tdb


async def is_suppressed(email: str) -> bool:
    return bool(email) and bool(await tdb.suppressions.find_one({"email": email.lower().strip()}))


async def log_comm(to: str, channel: str, template: str, subject: str, body: str,
                   kind: str = "transactional", lead_id=None, scheduled_for=None, extra=None):
    status = "simulated"
    if kind in ("marketing", "follow_up") and await is_suppressed(to):
        status = "blocked_opt_out"
    if scheduled_for:
        status = "scheduled"
    doc = {"to": to, "channel": channel, "template": template, "subject": subject, "body": body,
           "kind": kind, "status": status, "lead_id": lead_id, "scheduled_for": scheduled_for,
           "created_at": now_iso(), **(extra or {})}
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


def quote_email(name: str, quote: dict, link: str) -> str:
    lines = "\n".join(f"  - {l['label']}: £{l['amount']:.2f}" for l in quote["lines"])
    return (f"Hi {name},\n\nThank you for your enquiry with {company_name()}. Here is your quotation for "
            f"{quote['service_name']}:\n{lines}\n  Total: £{quote['total']:.2f}\n\n"
            f"Book an available slot here: {link}\n\nKind regards,\n{company_name()}")
