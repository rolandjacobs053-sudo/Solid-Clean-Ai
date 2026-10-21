import asyncio
import io
import json
import logging
import os
import re
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from emergentintegrations.llm.chat import StreamDone, TextDelta, UserMessage
from emergentintegrations.llm.openai import OpenAISpeechToText, OpenAITextToSpeech
from pydantic import BaseModel, Field

from ai import ai_complete, new_chat
from business_data import snapshot
from core import LLM_KEY, now_iso, oid, out, outs, require_owner, tdb

router = APIRouter(prefix="/api/admin/manager", dependencies=[Depends(require_owner)])
logger = logging.getLogger(__name__)
TAG_RE = re.compile(r"<<REMEMBER\s*(\{.*?\})\s*>>", re.S)
KINDS = ("target", "fact", "decision", "project", "preference")

SYSTEM = """You are the private AI Business Manager for {biz}, a UK cleaning company (residential/regular cleaning, end of tenancy, carpet and commercial cleaning). You speak only with the company owner inside the private dashboard. You act as a knowledgeable, direct business partner: operations, growth, marketing & sales, finance and performance.

HARD RULES
1. NEVER invent business figures. Use ONLY the numbers in LIVE BUSINESS DATA and BUSINESS MEMORY below. If a figure is missing or zero because nothing is recorded, say so and say exactly what needs recording or connecting (e.g. "record cleaner pay per job in Expenses & profit").
2. Label numbers clearly: "actual (recorded)" vs "estimate/assumption". When you forecast, list your assumptions.
3. Keep these distinct: revenue vs profit; enquiries vs confirmed bookings; one-off vs recurring; residential/regular vs end of tenancy; recommendations vs completed actions.
4. You cannot take actions. You can analyse, plan and DRAFT (emails, messages, proposals, ad copy, checklists). Never say you have sent, booked, changed, launched, published or paid for anything. Anything external (sending messages, publishing site changes, launching or paying for ads, changing prices/policies, confirming or changing bookings, purchases) needs the owner's explicit approval and is done by the owner in the dashboard.
5. No connected data exists for: Google Business Profile, Google Search Console, Google Ads account performance, Local Services Ads, accounting software or bank feeds. Do not claim to see them; recorded marketing spend in the dashboard is the only marketing cost data.
6. Be practical, specific and concise. No motivational filler. For recommendations, when useful, use a short table or list with: priority, action, expected benefit, estimated cost, difficulty, how to measure.
7. Long-term goal context: the owner wants to reach £10,000 monthly PROFIT and run the company without doing all the cleaning personally. Don't pretend it is quick; show the gap from current actual figures and the steps.
8. If records are tagged demo, they are excluded from the data; mention this if the owner asks why figures are low.
9. If the owner states a durable fact, target, decision or ongoing project worth remembering, add on its own line at the end:
<<REMEMBER {{"kind":"target|fact|decision|project|preference","text":"one concise sentence"}}>>
The owner then chooses whether to save it. Never mention the tag.
{voice}
GROWTH CONTEXT: Long-term ambition: £400m annual revenue OR £400m valuation (explain the difference when relevant: valuation = profit/EBITDA x a multiple; state the multiple as an assumption). Think like an experienced cleaning-industry entrepreneur, strategist, financial analyst, marketing director, operations manager and technology leader. Explain your reasoning and uncertainty. Prioritise actions that generate revenue, improve profit, build recurring contracts, create systems and increase company value.
CURRENT ROADMAP: {roadmap}
GOALS & PROGRESS (actual): {goals}
ALERTS DETECTED FROM DATA: {alerts}
DRAFTS WAITING FOR OWNER APPROVAL: {approvals} (in the Approvals tab - you cannot send them)

INDUSTRY KNOWLEDGE BASE (lessons retrieved from sources the owner's system has actually read; cite as 'per <source_title>' and respect evidence_level: verified/reported = sourced fact, claim/opinion = unproven). If the knowledge base has nothing relevant, say you're using general business knowledge and label it as such. Never claim to have read sources that are not listed here:
{knowledge}

BUSINESS MEMORY (saved by the owner; newest first):
{memory}

LIVE BUSINESS DATA (from the dashboard database, generated {today}):
{data}

OTHER RECENT CONVERSATION TITLES: {titles}

CONVERSATION SO FAR:
{transcript}"""
VOICE_NOTE = "\nVOICE MODE: the owner is speaking and will HEAR your reply. Answer in plain spoken sentences, at most about 120 words, no tables, no markdown, no lists longer than 3 items. Offer to give the full detail in text.\n"


class ChatIn(BaseModel):
    title: str = Field(default="", max_length=120)


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    via: Literal["text", "voice"] = "text"


class MemoryIn(BaseModel):
    kind: str = "fact"
    text: str = Field(min_length=2, max_length=500)


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class PriorityPatch(BaseModel):
    status: Optional[Literal["suggested", "approved", "dismissed", "completed"]] = None
    checklist: Optional[List[dict]] = None


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _chat(cid: str) -> dict:
    conv = out(await tdb.manager_chats.find_one({"_id": oid(cid)}))
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


async def _memory_text() -> str:
    mem = await tdb.manager_memory.find({}).sort("updated_at", -1).to_list(100)
    return "\n".join(f"- [{m['kind']}] {m['text']} (saved {m['updated_at'][:10]})" for m in mem) or "(nothing saved yet)"


async def _context(question: str = "") -> dict:
    from business_data import insights
    from routes_knowledge import relevant
    from routes_strategy import goals_with_progress
    s = await tdb.settings.find_one({}, {"business": 1})
    snap = await snapshot()
    rm = await tdb.roadmaps.find_one({}, {"current_stage": 1, "current_position": 1, "next_90_days": 1, "stages.n": 1, "stages.name": 1, "created_at": 1}, sort=[("created_at", -1)])
    roadmap = json.dumps({k: rm[k] for k in ("current_stage", "current_position", "next_90_days", "stages", "created_at") if k in rm}, default=str) if rm else "(not generated yet - owner can generate it in the Roadmap tab)"
    goals = [{k: g[k] for k in ("title", "current", "target", "progress_pct")} for g in await goals_with_progress(snap)]
    know = await relevant(question, 8) if question else []
    return {"biz": s["business"]["name"], "data": json.dumps(snap, default=str), "memory": await _memory_text(), "today": snap["today"], "roadmap": roadmap,
            "goals": json.dumps(goals), "alerts": json.dumps(insights(snap)), "approvals": await tdb.approvals.count_documents({"status": "pending"}),
            "knowledge": json.dumps(know) if know else "(no relevant lessons stored)"}


@router.get("/chats")
async def list_chats(q: str = ""):
    query = {"$or": [{"title": {"$regex": re.escape(q), "$options": "i"}}, {"messages.text": {"$regex": re.escape(q), "$options": "i"}}]} if q.strip() else {}
    docs = await tdb.manager_chats.find(query, {"messages": 0}).sort("updated_at", -1).to_list(200)
    return outs(docs)


@router.post("/chats")
async def create_chat(body: ChatIn):
    doc = {"title": body.title or "New conversation", "messages": [], "created_at": now_iso(), "updated_at": now_iso()}
    return {"id": str((await tdb.manager_chats.insert_one(doc)).inserted_id), **{k: doc[k] for k in ("title", "created_at")}}


@router.get("/chats/{cid}")
async def get_chat(cid: str):
    return await _chat(cid)


@router.patch("/chats/{cid}")
async def rename_chat(cid: str, body: ChatIn):
    await _chat(cid)
    await tdb.manager_chats.update_one({"_id": oid(cid)}, {"$set": {"title": body.title or "Untitled"}})
    return {"ok": True}


@router.delete("/chats/{cid}")
async def delete_chat(cid: str):
    res = await tdb.manager_chats.delete_one({"_id": oid(cid)})
    if not res.deleted_count:
        raise HTTPException(404, "Conversation not found")
    return {"ok": True}


@router.post("/chats/{cid}/messages")
async def send(cid: str, body: MessageIn):
    conv = await _chat(cid)
    ctx = await _context(body.text + " " + " ".join(m["text"] for m in conv["messages"][-2:] if m["role"] == "user"))
    titles = [c["title"] for c in await tdb.manager_chats.find({"_id": {"$ne": oid(cid)}}, {"title": 1}).sort("updated_at", -1).to_list(5)]
    transcript = "\n".join(f"{m['role'].upper()}: {m['text']}" for m in conv["messages"][-30:]) or "(new conversation)"
    system = SYSTEM.format(**ctx, voice=VOICE_NOTE if body.via == "voice" else "", titles=", ".join(titles) or "(none)", transcript=transcript)
    first = not conv["messages"]
    upd = {"$push": {"messages": {"role": "user", "text": body.text, "via": body.via, "at": now_iso()}}, "$set": {"updated_at": now_iso()}}
    if first and conv["title"] == "New conversation":
        upd["$set"]["title"] = body.text[:60] + ("…" if len(body.text) > 60 else "")
    await tdb.manager_chats.update_one({"_id": oid(cid)}, upd)
    chat = new_chat(system, f"mgr-{cid}")

    async def save(text: str, stopped: bool = False, error: bool = False, suggestions: list = ()):
        if text or stopped or error:
            await tdb.manager_chats.update_one({"_id": oid(cid)}, {"$push": {"messages": {"role": "assistant", "text": text, "via": body.via, "stopped": stopped, "error": error, "suggestions": list(suggestions), "at": now_iso()}},
                                                                    "$set": {"updated_at": now_iso()}})

    async def gen():
        full, finished = "", False
        try:
            async for ev in chat.stream_message(UserMessage(text=body.text)):
                if isinstance(ev, TextDelta):
                    full += ev.content
                    yield _sse({"type": "delta", "text": ev.content})
                elif isinstance(ev, StreamDone):
                    break
            finished = True
            clean = TAG_RE.sub("", full).strip()
            suggestions = []
            for raw in TAG_RE.findall(full):
                try:
                    m = json.loads(raw)
                    suggestions.append({"kind": m.get("kind") if m.get("kind") in KINDS else "fact", "text": str(m.get("text", ""))[:500]})
                except json.JSONDecodeError:
                    pass
            for s in suggestions:
                yield _sse({"type": "memory_suggestion", **s})
            await save(clean, suggestions=suggestions)
            yield _sse({"type": "done", "text": clean})
        except Exception:
            logger.exception("manager stream failed")
            finished = True
            await save(TAG_RE.sub("", full).strip(), error=True)
            yield _sse({"type": "error", "text": "The AI service didn't respond. Please try again in a moment. If this keeps happening, check your Universal Key balance."})
        finally:
            if not finished:
                await asyncio.shield(save(TAG_RE.sub("", full).strip(), stopped=True))

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) < 1500:
        raise HTTPException(400, "Recording was too short - please hold the mic a little longer.")
    if len(data) > 24 * 1024 * 1024:
        raise HTTPException(400, "Recording is too long - please keep voice messages under a few minutes.")
    ct, fn = (file.content_type or "").lower(), (file.filename or "").lower()
    ext = next((e for e, keys in (("mp4", ("mp4", "m4a", "aac")), ("mp3", ("mpeg", "mp3")), ("wav", ("wav",)), ("ogg", ("ogg",))) if any(k in ct or fn.endswith(k) for k in keys)), "webm")
    buf = io.BytesIO(data)
    buf.name = f"speech.{ext}"
    try:
        res = await OpenAISpeechToText(api_key=LLM_KEY).transcribe(file=buf, model="whisper-1", response_format="json", language="en",
                                                                   prompt="UK cleaning business owner talking about bookings, end of tenancy, carpet cleaning, profit, Solid Clean Ltd.")
    except Exception:
        logger.exception("transcription failed")
        raise HTTPException(502, "Speech recognition failed. Please try again or type your message.")
    text = (res.text or "").strip()
    if not text:
        raise HTTPException(422, "I couldn't hear anything - please try again closer to the microphone.")
    return {"text": text}


def _speakable(text: str) -> str:
    t = re.sub(r"```.*?```", " ", text, flags=re.S)
    t = re.sub(r"\|", " ", t)
    t = re.sub(r"^[-:\s|]+$", " ", t, flags=re.M)
    t = re.sub(r"[#*_`>]+", "", t)
    t = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:4000]


@router.post("/speak")
async def speak(body: SpeakIn):
    text = _speakable(body.text)
    if not text:
        raise HTTPException(400, "Nothing to read aloud")
    try:
        audio = await OpenAITextToSpeech(api_key=LLM_KEY).generate_speech(text=text, model="tts-1", voice=os.environ.get("MANAGER_TTS_VOICE", "sage"), response_format="mp3")
    except Exception:
        logger.exception("tts failed")
        raise HTTPException(502, "Voice playback failed. The written answer is still shown.")
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


@router.get("/memory")
async def list_memory():
    return outs(await tdb.manager_memory.find({}).sort("updated_at", -1).to_list(200))


@router.post("/memory")
async def add_memory(body: MemoryIn):
    kind = body.kind if body.kind in KINDS else "fact"
    existing = await tdb.manager_memory.find_one({"text": body.text.strip()}, {"_id": 1})
    if existing:
        await tdb.manager_memory.update_one({"_id": existing["_id"]}, {"$set": {"kind": kind, "updated_at": now_iso()}})
        return {"id": str(existing["_id"]), "existing": True}
    doc = {"kind": kind, "text": body.text.strip(), "created_at": now_iso(), "updated_at": now_iso()}
    return {"id": str((await tdb.manager_memory.insert_one(doc)).inserted_id)}


@router.put("/memory/{mid}")
async def edit_memory(mid: str, body: MemoryIn):
    res = await tdb.manager_memory.update_one({"_id": oid(mid)}, {"$set": {"kind": body.kind if body.kind in KINDS else "fact", "text": body.text.strip(), "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(404, "Memory item not found")
    return {"ok": True}


@router.delete("/memory/{mid}")
async def delete_memory(mid: str):
    res = await tdb.manager_memory.delete_one({"_id": oid(mid)})
    if not res.deleted_count:
        raise HTTPException(404, "Memory item not found")
    return {"ok": True}


@router.get("/snapshot")
async def get_snapshot():
    return await snapshot()


PRIORITY_SYSTEM = """You are the AI Business Manager for {biz}. Using ONLY the data and memory below, choose the 3 most valuable actions the owner should take now to grow profit and reduce dependence on the owner doing the cleaning. Never invent figures; if data is missing, one action may be to start recording it. Use "estimate" wording for anything not in the data.
Return ONLY a JSON array of up to 3 objects with keys: "title" (max 8 words), "what" (what to do, 1-2 sentences), "why" (why it matters, citing actual figures where available), "benefit" (expected benefit, labelled estimate), "cost" (estimated cost in GBP or "Free" or "Unknown"), "priority" ("high"|"medium"|"low"), "measure" (how to measure success).
Avoid repeating these recently dismissed or completed actions: {avoid}

MEMORY:
{memory}

GOALS: {goals}
ALERTS: {alerts}

DATA ({today}):
{data}"""


def _json(text: str, opener: str):
    closer = "]" if opener == "[" else "}"
    s, e = text.find(opener), text.rfind(closer)
    if s < 0 or e < s:
        raise ValueError("no json")
    return json.loads(text[s:e + 1])


@router.get("/priorities")
async def list_priorities():
    return outs(await tdb.priorities.find({}).sort("created_at", -1).to_list(100))


@router.post("/priorities/generate")
async def generate_priorities():
    ctx = await _context()
    avoid = [p["title"] for p in await tdb.priorities.find({"status": {"$in": ["dismissed", "completed"]}}).sort("created_at", -1).to_list(15)]
    try:
        raw = await ai_complete(PRIORITY_SYSTEM.format(**ctx, avoid=", ".join(avoid) or "(none)"), "Give my top 3 business priorities now, taking the ALERTS and GOALS into account.")
        items = _json(raw, "[")[:3]
    except Exception:
        logger.exception("priorities failed")
        raise HTTPException(502, "Couldn't generate priorities right now. Please try again.")
    await tdb.priorities.delete_many({"status": "suggested"})
    keys = ("title", "what", "why", "benefit", "cost", "priority", "measure")
    for it in items:
        doc = {k: str(it.get(k, ""))[:600] for k in keys}
        doc["priority"] = doc["priority"].lower() if doc["priority"].lower() in ("high", "medium", "low") else "medium"
        await tdb.priorities.insert_one({**doc, "status": "suggested", "checklist": [], "created_at": now_iso(), "updated_at": now_iso()})
    return await list_priorities()


@router.patch("/priorities/{pid}")
async def update_priority(pid: str, body: PriorityPatch):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if "checklist" in upd:
        upd["checklist"] = [{"text": str(i.get("text", ""))[:300], "done": bool(i.get("done"))} for i in upd["checklist"]][:20]
    res = await tdb.priorities.update_one({"_id": oid(pid)}, {"$set": {**upd, "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(404, "Priority not found")
    return out(await tdb.priorities.find_one({"_id": oid(pid)}))


@router.post("/priorities/{pid}/plan")
async def plan_priority(pid: str):
    p = await tdb.priorities.find_one({"_id": oid(pid)})
    if not p:
        raise HTTPException(404, "Priority not found")
    ctx = await _context()
    system = f"You turn a business recommendation for {ctx['biz']} into a practical checklist. Return ONLY a JSON array of 4-8 short imperative steps (strings). Steps that involve sending, publishing, spending or changing records must start with 'Owner approves & ' . Never invent figures.\nDATA: {ctx['data'][:6000]}"
    try:
        steps = _json(await ai_complete(system, f"Recommendation: {p['title']}. {p['what']} Measure: {p['measure']}"), "[")
    except Exception:
        logger.exception("plan failed")
        raise HTTPException(502, "Couldn't build the checklist right now. Please try again.")
    checklist = [{"text": str(s)[:300], "done": False} for s in steps][:8]
    await tdb.priorities.update_one({"_id": p["_id"]}, {"$set": {"checklist": checklist, "updated_at": now_iso()}})
    return out(await tdb.priorities.find_one({"_id": p["_id"]}))
