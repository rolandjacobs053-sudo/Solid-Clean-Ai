import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from emergentintegrations.llm.chat import StreamDone, TextDelta, UserMessage
from pydantic import BaseModel, Field

from ai import new_chat
from comms import add_event, upsert_lead
from core import company_name, current_company, get_settings, now_iso, oid, plan_features, tdb
from pricing import compute_quote
from routes_public import notify_owner, store_quote, tenant_from_slug


async def chat_enabled(slug: str):
    company = await tenant_from_slug(slug)
    if not company.get("comped") and "ai_receptionist" not in await plan_features(company):
        raise HTTPException(403, "AI receptionist is not enabled for this company")


router = APIRouter(prefix="/api/public/{slug}/chat", dependencies=[Depends(chat_enabled)])
logger = logging.getLogger(__name__)
TAG_RE = re.compile(r"<<(QUOTE|LEAD|ESCALATE)\s*(\{.*?\})\s*>>", re.S)
def greeting():
    return f"Hello, you're through to {company_name()}. I'm the virtual receptionist - I can explain our services, work out an exact quote from our price list, and help you book. How can I help today?"

SYSTEM = """You are the virtual receptionist for {biz}, a professional cleaning company. Be warm, professional and concise (2-4 short sentences).

KNOWLEDGE BASE (your ONLY source of company facts):
{kb}

SERVICE KEYS: {services}
PROPERTY TYPE KEYS: {ptypes}
CONDITION KEYS: {conds}
EXTRA KEYS: {extras}
PUBLISHED POLICIES (quote only these; never change them):
{policies}

STRICT RULES:
1. NEVER state, estimate or guess a price. Prices come ONLY from the quoting system.
2. To quote, collect: service, property type, bedrooms, bathrooms, living rooms, condition, extras (can be none), postcode. Never ask about parking. Ask one or two questions at a time. When you have everything, write a short line saying you're calculating it, then on its own line output exactly:
<<QUOTE {{"service":"key","property_type":"key","bedrooms":0,"bathrooms":0,"living_rooms":0,"condition":"key","extras":[],"postcode":"..."}}>>
The customer then sees the exact quote card and you receive the result as a SYSTEM note.
3. NEVER confirm a booking or promise a date/time. To book, ask the customer to press "Book this quote" on the quote card - live availability is checked there and payment confirms the booking.
4. As soon as you know the customer's name AND phone or email, output once:
<<LEAD {{"name":"...","phone":"...","email":"...","postcode":"...","summary":"one-line enquiry summary"}}>>
5. Hand over to a human for complaints, commercial/office contracts, damage, refunds, very heavy soiling, out-of-area postcodes, or anything not in the knowledge base. Output <<ESCALATE {{"reason":"..."}}>>, tell the customer a team member will call back, and ask for their phone number if you don't have it.
6. If unsure, say so and offer a callback. Never invent policies, services or availability.
7. The << >> tags are hidden from the customer - never mention them."""


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class EscalateIn(BaseModel):
    name: str = ""
    phone: str = ""
    reason: str = "Customer asked to speak to a person"


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _system(s: dict, conv: dict, policies: str = "") -> str:
    p = s["pricing"]
    keys = lambda items: ", ".join(f"{i['key']} ({i['name']})" for i in items)
    kb = "\n".join(f"- Q: {k['q']} A: {k['a']}" for k in s["knowledge_base"])
    transcript = "\n".join(f"{m['role'].upper()}: {m['text']}" for m in conv["messages"][-30:])
    services = [x for x in p["services"] if x.get("active", True) and x.get("online_booking", True)]
    return (SYSTEM.format(biz=s["business"]["name"], kb=kb, services=keys(services), policies=policies or "(none published)", ptypes=keys(p["property_types"]),
                          conds=keys(p["conditions"]), extras=keys(p["extras"]))
            + f"\n\nCONVERSATION SO FAR:\n{transcript or '(none)'}")


async def published_policies() -> str:
    return "\n".join([f"- {x['title']}: {x['published_content'][:4000]}" async for x in tdb.policies.find({"audience": "public", "published_version": {"$gt": 0}, "unpublished": {"$ne": True}})])


async def _conv(cid: str) -> dict:
    conv = await tdb.conversations.find_one({"_id": oid(cid)})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.post("/sessions")
async def start_session():
    doc = {"channel": "web_chat", "status": "open", "escalated": False, "lead_id": None, "summary": "",
           "messages": [{"role": "assistant", "text": greeting(), "at": now_iso()}], "created_at": now_iso(), "updated_at": now_iso()}
    cid = str((await tdb.conversations.insert_one(doc)).inserted_id)
    return {"id": cid, "greeting": doc["messages"][0]["text"]}


async def _handle_tags(full: str, conv: dict, s: dict):
    cid, events, notes = str(conv["_id"]), [], []
    lead_id = conv.get("lead_id")
    for kind, raw in TAG_RE.findall(full):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if kind == "QUOTE":
            result = compute_quote(s["pricing"], data)
            if result["status"] == "invalid":
                notes.append("QUOTE FAILED: invalid service key - ask the customer again.")
                continue
            qid, tok = await store_quote(data, result, lead_id, "ai_chat", cid)
            events.append({"type": "quote", "quote_id": qid, "token": tok, "result": result})
            notes.append(f"QUOTE RESULT: status={result['status']} total=" + (f"£{result['total']:.2f}" if result.get("total") else "n/a")
                         + (f" reasons={result['reasons']}" if result["reasons"] else ""))
        elif kind == "LEAD":
            lead_id = await upsert_lead(data, "ai_chat", f"AI receptionist enquiry: {data.get('summary', '')}")
            await tdb.quotes.update_many({"conversation_id": cid}, {"$set": {"lead_id": lead_id}})
            await tdb.conversations.update_one({"_id": conv["_id"]}, {"$set": {"lead_id": lead_id, "summary": data.get("summary", "")}})
            await notify_owner(s, "New enquiry via AI receptionist", f"{data.get('name')} {data.get('phone') or ''} {data.get('email') or ''}: {data.get('summary', '')}", lead_id)
            events.append({"type": "lead"})
        elif kind == "ESCALATE":
            await tdb.conversations.update_one({"_id": conv["_id"]}, {"$set": {"escalated": True, "escalation_reason": data.get("reason", ""), "status": "needs_human"}})
            await add_event(lead_id, "escalation", f"Escalated to human: {data.get('reason', '')}")
            await notify_owner(s, "AI receptionist escalation", f"Conversation {cid}: {data.get('reason', '')}", lead_id)
            events.append({"type": "escalated"})
    return events, notes


@router.post("/sessions/{cid}/messages")
async def send_message(cid: str, body: MessageIn):
    conv = await _conv(cid)
    s = await get_settings()
    chat = new_chat(_system(s, conv, await published_policies()), f"conv-{cid}")
    await tdb.conversations.update_one({"_id": conv["_id"]}, {"$push": {"messages": {"role": "user", "text": body.text, "at": now_iso()}}})

    async def gen():
        full = ""
        try:
            async for ev in chat.stream_message(UserMessage(text=body.text)):
                if isinstance(ev, TextDelta):
                    full += ev.content
                    yield _sse({"type": "delta", "text": ev.content})
                elif isinstance(ev, StreamDone):
                    break
        except Exception:
            logger.exception("chat stream failed")
            yield _sse({"type": "error", "text": "Sorry, I'm having trouble right now. Please try again or request a call back."})
            return
        clean = TAG_RE.sub("", full).strip()
        events, notes = await _handle_tags(full, conv, s)
        msgs = [{"role": "assistant", "text": clean, "at": now_iso()}] + [{"role": "system", "text": n, "at": now_iso()} for n in notes]
        await tdb.conversations.update_one({"_id": conv["_id"]}, {"$push": {"messages": {"$each": msgs}}, "$set": {"updated_at": now_iso()}})
        for e in events:
            yield _sse(e)
        yield _sse({"type": "done", "text": clean})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/sessions/{cid}/escalate")
async def escalate(cid: str, body: EscalateIn):
    conv = await _conv(cid)
    s = await get_settings()
    lead_id = conv.get("lead_id")
    if body.phone:
        lead_id = await upsert_lead({"name": body.name, "phone": body.phone}, "ai_chat", f"Call-back requested: {body.reason}")
    await tdb.conversations.update_one({"_id": conv["_id"]}, {"$set": {"escalated": True, "status": "needs_human", "escalation_reason": body.reason, "lead_id": lead_id},
                                                            "$push": {"messages": {"role": "system", "text": f"Customer requested a human: {body.reason}", "at": now_iso()}}})
    await notify_owner(s, "Call-back requested", f"{body.name or 'Customer'} {body.phone or ''}: {body.reason}", lead_id)
    return {"ok": True, "message": "Thanks - a member of our team will call you back as soon as possible."}
