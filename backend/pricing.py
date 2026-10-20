import re
from datetime import date, timedelta, datetime

from core import now, tdb

DEFAULT_SETTINGS = {
    "key": "main",
    "business": {
        "name": "[Company name]",
        "website": "[Website URL]",
        "booking_page": "",
        "online_payments": True,
        "payment_instructions": "[Payment instructions, e.g. bank transfer details or pay on the day]",
        "phone": "[Business phone - placeholder]",
        "email": "[Business email - placeholder]",
        "owner_notify_email": "[Owner notification email - placeholder]",
        "review_link": "[Google review link - placeholder]",
        "voice_number": "",
        "follow_up_after_hours": 48,
        "max_follow_ups": 2,
    },
    "pricing": {
        "currency": "GBP",
        "placeholder_notice": "Placeholder prices - replace with your approved price list",
        "services": [
            {"key": "regular", "name": "Residential / Regular Clean", "base": 45, "per_bedroom": 12, "per_bathroom": 10, "per_living_room": 8, "min_price": 60, "requires_survey": False},
            {"key": "end_of_tenancy", "name": "End of Tenancy Clean", "base": 120, "per_bedroom": 35, "per_bathroom": 30, "per_living_room": 20, "min_price": 180, "requires_survey": False},
            {"key": "carpet", "name": "Carpet Cleaning", "base": 40, "per_bedroom": 30, "per_bathroom": 0, "per_living_room": 35, "min_price": 100, "from_price": 100, "requires_survey": True},
            {"key": "commercial", "name": "Commercial / Office Cleaning", "base": 0, "per_bedroom": 0, "per_bathroom": 0, "per_living_room": 0, "min_price": 0, "requires_survey": True},
        ],
        "property_types": [
            {"key": "studio", "name": "Studio", "multiplier": 0.9},
            {"key": "flat", "name": "Flat / Apartment", "multiplier": 1.0},
            {"key": "maisonette", "name": "Maisonette", "multiplier": 1.05},
            {"key": "house", "name": "House", "multiplier": 1.12},
        ],
        "conditions": [
            {"key": "good", "name": "Well maintained", "multiplier": 1.0, "requires_review": False},
            {"key": "average", "name": "Average", "multiplier": 1.15, "requires_review": False},
            {"key": "poor", "name": "Needs extra attention", "multiplier": 1.35, "requires_review": False},
            {"key": "very_poor", "name": "Very heavy soiling", "multiplier": 1.0, "requires_review": True},
        ],
        "extras": [
            {"key": "oven", "name": "Single oven deep clean", "price": 45},
            {"key": "double_oven", "name": "Double oven deep clean", "price": 65},
            {"key": "fridge", "name": "Fridge/freezer cleaning", "price": 25, "description": "Inside and outside clean of your fridge/freezer. No defrosting."},
            {"key": "freezer_defrost", "name": "Freezer defrost", "price": 75, "excludes": ["fridge"],
             "description": "For iced-up freezers: we defrost the freezer, then clean the fridge/freezer inside and out. Includes fridge/freezer cleaning, so you don't need both."},
            {"key": "hob", "name": "Hob cleaning", "price": 25},
            {"key": "dishwasher", "name": "Dishwasher clean", "price": 20},
            {"key": "blinds", "name": "Blinds cleaning", "price": 20},
            {"key": "windows", "name": "Interior windows", "price": 30},
            {"key": "cabinets", "name": "Inside kitchen cabinets", "price": 25},
            {"key": "balcony", "name": "Balcony / patio", "price": 25},
            {"key": "supplies", "name": "Cleaning supplies & equipment", "price": 25},
        ],
        "short_notice": {"days": 2, "type": "percent", "value": 0},
        "promo_codes": [],
        "service_area_prefixes": [],
    },
    "availability": {
        "working_days": [0, 1, 2, 3, 4, 5],
        "slots": ["08:00", "11:00", "14:00"],
        "capacity_per_slot": 2,
        "min_notice_days": 1,
        "max_advance_days": 60,
        "blocked_dates": [],
    },
    "knowledge_base": [
        {"q": "How do I book a cleaning service?", "a": "Get an instant quote online, choose an available date and time, and pay securely to confirm. It only takes a minute."},
        {"q": "Do I need to provide cleaning supplies?", "a": "Cleaning supplies are not included as standard. You can add cleaning supplies & equipment as an extra when booking, or provide your own."},
        {"q": "Can I reschedule or cancel?", "a": "Yes - please contact us at least 24 hours in advance to reschedule or cancel."},
        {"q": "How do I pay?", "a": "[Describe your payment policy]"},
        {"q": "Which areas do you cover?", "a": "[Describe your service area]"},
    ],
}


SERVICE_DEFAULTS = {"description": "", "pricing_mode": "per_room", "fixed_price": 0, "active": True, "online_booking": True,
                    "internal_notes": "", "extras": [], "scope_included": "", "scope_excluded": "", "preparation": ""}


def _find(items, key):
    return next((i for i in items if i["key"] == key), None)


def postcode_prefix(postcode: str) -> str:
    m = re.match(r"^\s*([A-Za-z]{1,2})", postcode or "")
    return m.group(1).upper() if m else ""


def compute_quote(pricing: dict, q: dict, public: bool = True) -> dict:
    svc = _find(pricing["services"], q.get("service"))
    if svc:
        svc = {**SERVICE_DEFAULTS, **svc}
    if not svc or not svc["active"] or (public and not svc["online_booking"]):
        return {"status": "invalid", "total": None, "lines": [], "reasons": ["Unknown or unavailable service"], "currency": "GBP"}
    result = {"service_name": svc["name"], "currency": pricing["currency"], "lines": [], "reasons": []}
    if svc.get("requires_survey"):
        result.update(status="needs_review", total=None, reasons=["This service is quoted after a short survey."])
        return result
    ptype = _find(pricing["property_types"], q.get("property_type")) or pricing["property_types"][1]
    cond = _find(pricing["conditions"], q.get("condition")) or pricing["conditions"][0]
    beds, baths, livs = int(q.get("bedrooms", 0)), int(q.get("bathrooms", 1)), int(q.get("living_rooms", 1))
    if svc["pricing_mode"] == "per_room":
        lines = [
            {"label": f"{svc['name']} - base", "amount": svc["base"]},
            {"label": f"{beds} bedroom(s)", "amount": beds * svc["per_bedroom"]},
            {"label": f"{baths} bathroom(s)", "amount": baths * svc["per_bathroom"]},
            {"label": f"{livs} living room(s)", "amount": livs * svc["per_living_room"]},
        ]
        subtotal = sum(line["amount"] for line in lines)
        adjust = round(subtotal * ptype["multiplier"] * cond["multiplier"] - subtotal, 2)
        if adjust:
            lines.append({"label": f"{ptype['name']} / {cond['name']} adjustment", "amount": adjust})
    else:
        lines = [{"label": svc["name"] + (" (starting price)" if svc["pricing_mode"] == "from" else ""), "amount": svc["fixed_price"]}]
    allowed = svc["extras"] or [e["key"] for e in pricing["extras"]]
    chosen = [k for k in dict.fromkeys(q.get("extras") or []) if k in allowed and _find(pricing["extras"], k)]
    excluded = {x for k in chosen for x in _find(pricing["extras"], k).get("excludes", [])}
    qtys = q.get("extra_qty") or {}
    for key in chosen:
        if key not in excluded:
            extra = _find(pricing["extras"], key)
            price = max(float(extra.get("price") or 0), 0)
            try:
                cap = max(int(extra.get("max_qty") or 20), 1)
            except (TypeError, ValueError):
                cap = 20
            n = max(1, min(int(qtys.get(key) or 1), cap)) if extra.get("per_item") else 1
            lines.append({"label": extra["name"] + (f" × {n}" if extra.get("per_item") else ""), "amount": round(price * n, 2)})
    total = round(sum(line["amount"] for line in lines), 2)
    if total < svc["min_price"]:
        lines.append({"label": "Minimum booking value top-up", "amount": round(svc["min_price"] - total, 2)})
        total = float(svc["min_price"])
    sn = pricing.get("short_notice") or {}
    if q.get("date") and sn.get("value"):
        try:
            if (date.fromisoformat(q["date"]) - now().date()).days <= sn["days"]:
                amt = round(total * sn["value"] / 100, 2) if sn["type"] == "percent" else float(sn["value"])
                lines.append({"label": "Short-notice surcharge", "amount": amt})
                total = round(total + amt, 2)
        except ValueError:
            pass
    code = (q.get("promo_code") or "").strip().upper()
    if code:
        promo = next((p for p in pricing.get("promo_codes", []) if p["code"].upper() == code and p.get("active")
                      and (not p.get("expires") or p["expires"] >= now().date().isoformat())
                      and (not p.get("max_uses") or p.get("uses", 0) < p["max_uses"])), None)
        if promo:
            off = round(total * promo["value"] / 100, 2) if promo["type"] == "percent" else min(float(promo["value"]), total)
            lines.append({"label": f"Promo {promo['code'].upper()}", "amount": -off})
            total = round(total - off, 2)
            result["promo_applied"] = promo["code"].upper()
        else:
            result["promo_error"] = "Promo code not valid"
    reasons = []
    if svc["pricing_mode"] == "from":
        reasons.append("This is a starting price - our team will confirm the final price.")
    if cond.get("requires_review"):
        reasons.append("Property condition needs a quick review by our team before a fixed price.")
    if q.get("postcode") and pricing["service_area_prefixes"] and postcode_prefix(q["postcode"]) not in pricing["service_area_prefixes"]:
        reasons.append("This postcode is outside our standard service area - our team will confirm.")
    result.update(status="needs_review" if reasons else "ok", total=float(total), lines=[l for l in lines if l["amount"]], reasons=reasons)
    return result


def _active_booking_filter(day: str):
    cutoff = (now().replace(microsecond=0)).isoformat()
    return {"date": day, "$or": [
        {"status": {"$in": ["confirmed", "awaiting_approval"]}},
        {"status": "pending_payment", "hold_expires_at": {"$gt": cutoff}},
    ]}


async def slots_for(av: dict, day: str) -> list:
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return []
    today = now().date()
    if d.weekday() not in av["working_days"] or day in av["blocked_dates"]:
        return []
    if d < today + timedelta(days=av["min_notice_days"]) or d > today + timedelta(days=av["max_advance_days"]):
        return []
    counts = {}
    async for b in tdb.bookings.find(_active_booking_filter(day), {"slot": 1}):
        counts[b["slot"]] = counts.get(b["slot"], 0) + 1
    return [{"slot": s, "remaining": av["capacity_per_slot"] - counts.get(s, 0)} for s in av["slots"]
            if av["capacity_per_slot"] - counts.get(s, 0) > 0]


def fmt_date(day: str) -> str:
    return datetime.fromisoformat(day).strftime("%a %d %b %Y")
