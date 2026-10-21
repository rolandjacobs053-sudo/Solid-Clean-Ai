import json
import logging
import os
import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from emergentintegrations.llm.chat import UserMessage
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Gather, VoiceResponse

from ai import new_chat
from comms import booking_link, log_comm, quote_email
from core import company_name, db, get_settings, now_iso, oid, plan_features, require_admin, set_tenant, tdb
from routes_chat import TAG_RE, _handle_tags, _system, greeting, published_policies

router = APIRouter(prefix="/api/voice")
admin = APIRouter(prefix="/api/admin/voice", dependencies=[Depends(require_admin)])
logger = logging.getLogger(__name__)
VOICE = {"voice": "Polly.Amy-Neural", "language": "en-GB"}
END_RE = re.compile(r"<<END\s*(\{.*?\})?\s*>>", re.S)
VOICE_RULES = """

PHONE CALL MODE (overrides the web-chat instructions above):
- You are speaking on the telephone. Use 1-3 short spoken sentences. No lists, symbols, emojis or markdown.
- There is no quote card and no "Book this quote" button. After you output a QUOTE tag the system itself reads the exact price to the caller, so never say a price yourself.
- To book, the caller receives the quote by email with a link to choose a date and time and pay. Ask for their email address and ask them to spell it, then include it in the LEAD tag.
- Caller's phone number from the network: {caller}. Use it in the LEAD tag unless they give a different number.
- When the caller has finished or says goodbye, thank them warmly and output <<END {{}}>>."""


def _xml(vr: VoiceResponse) -> Response:
    return Response(content=str(vr), media_type="application/xml")


def _digits(number: str) -> str:
    d = re.sub(r"\D", "", number or "")
    return "44" + d[1:] if d.startswith("0") else d


async def _params(request: Request) -> dict:
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not token:
        raise HTTPException(503, "Phone receptionist is not configured")
    params = {str(k): str(v) for k, v in (await request.form()).items()}
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    url = f"https://{host}{request.url.path}" + (f"?{request.url.query}" if request.url.query else "")
    if not RequestValidator(token).validate(url, params, request.headers.get("X-Twilio-Signature", "")):
        raise HTTPException(403, "Invalid Twilio signature")
    return params


def _gather(vr: VoiceResponse, slug: str, cid: str, text: str):
    g = Gather(input="speech", action=f"/api/voice/{slug}/{cid}/speech", method="POST", speech_timeout="auto",
               timeout=6, action_on_empty_result=True, language="en-GB", speech_model="phone_call")
    g.say(text, **VOICE)
    vr.append(g)


def _goodbye(vr: VoiceResponse, text: str) -> Response:
    vr.say(text, **VOICE)
    vr.hangup()
    return _xml(vr)


async def _company_for(to: str):
    target = _digits(to)
    async for s in db.settings.find({"business.voice_number": {"$nin": ["", None]}}, {"company_id": 1, "business.voice_number": 1}):
        if target and _digits(s["business"]["voice_number"]) == target:
            return await db.companies.find_one({"_id": oid(s["company_id"])})
    return None


@router.post("/incoming")
async def incoming(request: Request):
    p = await _params(request)
    company = await _company_for(p.get("To", ""))
    vr = VoiceResponse()
    if not company or company.get("suspended"):
        return _goodbye(vr, "Sorry, this line is not available at the moment. Goodbye.")
    set_tenant(company)
    if not company.get("comped") and "ai_receptionist" not in await plan_features(company):
        return _goodbye(vr, f"Thank you for calling {company_name()}. Please call back during business hours. Goodbye.")
    conv = await tdb.conversations.find_one({"call_sid": p.get("CallSid")})
    if not conv:
        conv = {"channel": "phone", "call_sid": p.get("CallSid"), "caller": p.get("From", ""), "status": "open", "escalated": False,
                "lead_id": None, "summary": "", "silent_turns": 0, "messages": [{"role": "assistant", "text": greeting(), "at": now_iso()}],
                "created_at": now_iso(), "updated_at": now_iso()}
        conv["_id"] = (await tdb.conversations.insert_one(conv)).inserted_id
    _gather(vr, company["slug"], str(conv["_id"]), greeting())
    return _xml(vr)


def _money(v: float) -> str:
    return f"£{v:,.2f}".replace(".00", "")


async def _email_quote(conv: dict, request: Request, slug: str) -> bool:
    if not conv.get("lead_id"):
        return False
    lead = await tdb.leads.find_one({"_id": oid(conv["lead_id"])})
    q = await tdb.quotes.find_one({"conversation_id": str(conv["_id"]), "status": "sent", "emailed": {"$ne": True}}, sort=[("created_at", -1)])
    if not lead or not lead.get("email") or not q:
        return False
    tok = q.get("token") or secrets.token_urlsafe(16)
    await log_comm(lead["email"], "email", "quote_sent", f"Your {company_name()} quote - £{q['total']:.2f}",
                   quote_email(lead.get("name") or "there", q["result"]), lead_id=conv["lead_id"], link=booking_link(request, slug, str(q["_id"]), tok))
    await tdb.quotes.update_one({"_id": q["_id"]}, {"$set": {"emailed": True, "token": tok}})
    return True


async def _reply(conv: dict, said: str, request: Request, slug: str) -> tuple:
    s = await get_settings()
    system = _system(s, conv, await published_policies()) + VOICE_RULES.format(caller=conv.get("caller") or "unknown")
    await tdb.conversations.update_one({"_id": conv["_id"]}, {"$push": {"messages": {"role": "user", "text": said, "at": now_iso()}}, "$set": {"silent_turns": 0}})
    full = await new_chat(system, f"call-{conv['_id']}").send_message(UserMessage(text=said))
    events, notes = await _handle_tags(full, conv, s)
    text = END_RE.sub("", TAG_RE.sub("", full)).strip()
    for e in events:
        if e["type"] == "quote":
            r = e["result"]
            text += (f" Your quote comes to {_money(r['total'])}, including everything we discussed." if r["status"] == "ok"
                     else " That one needs a quick review by our team, so someone will call you back with an exact price.")
    conv = await tdb.conversations.find_one({"_id": conv["_id"]})
    if await _email_quote(conv, request, slug):
        text += " I've emailed your quote with a link to choose a date and time and pay securely."
    ended = bool(END_RE.search(full)) or any(e["type"] == "escalated" for e in events)
    msgs = [{"role": "assistant", "text": text, "at": now_iso()}] + [{"role": "system", "text": n, "at": now_iso()} for n in notes]
    upd = {"$push": {"messages": {"$each": msgs}}, "$set": {"updated_at": now_iso()}}
    if ended and conv["status"] == "open":
        upd["$set"]["status"] = "resolved"
    await tdb.conversations.update_one({"_id": conv["_id"]}, upd)
    return text, ended


@router.post("/{slug}/{cid}/speech")
async def speech(slug: str, cid: str, request: Request):
    p = await _params(request)
    company = await db.companies.find_one({"slug": slug})
    if not company:
        raise HTTPException(404, "Unknown company")
    set_tenant(company)
    conv = await tdb.conversations.find_one({"_id": oid(cid), "channel": "phone"})
    if not conv:
        raise HTTPException(404, "Call not found")
    vr = VoiceResponse()
    said = p.get("SpeechResult", "").strip()
    if not said:
        if conv.get("silent_turns", 0) >= 2:
            return _goodbye(vr, f"Sorry, I can't hear you. Please call {company_name()} back any time. Goodbye.")
        await tdb.conversations.update_one({"_id": conv["_id"]}, {"$inc": {"silent_turns": 1}})
        _gather(vr, slug, cid, "Sorry, I didn't catch that. How can I help?")
        return _xml(vr)
    try:
        text, ended = await _reply(conv, said, request, slug)
    except Exception:
        logger.exception("voice reply failed")
        await tdb.conversations.update_one({"_id": conv["_id"]}, {"$set": {"status": "needs_human", "escalated": True, "escalation_reason": "Voice assistant error"}})
        return _goodbye(vr, "Sorry, I'm having trouble right now. A member of our team will call you back shortly. Goodbye.")
    if ended:
        return _goodbye(vr, text or "Thank you for calling. Goodbye.")
    _gather(vr, slug, cid, text or "How else can I help?")
    return _xml(vr)


@admin.get("/status")
async def voice_status(request: Request):
    s = await get_settings()
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    return {"configured": bool(os.environ.get("TWILIO_AUTH_TOKEN")), "voice_number": s["business"].get("voice_number", ""),
            "webhook_url": f"https://{host}/api/voice/incoming"}
