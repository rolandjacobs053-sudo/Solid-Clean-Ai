import asyncio
import hashlib
import ipaddress
import json
import logging
import re
from html import unescape
from typing import Literal, Optional
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ai import ai_complete
from core import now, now_iso, oid, out, outs, require_owner, tdb

router = APIRouter(prefix="/api/admin/knowledge", dependencies=[Depends(require_owner)])
logger = logging.getLogger(__name__)
SOURCE_TYPES = ("web", "youtube", "book", "podcast", "social", "report", "case_study", "course", "other")
LEVELS = ("verified", "reported", "claim", "opinion")
BLOCKED = ("tiktok.com", "instagram.com", "facebook.com", "linkedin.com", "x.com", "twitter.com")
FIELDS = ("title", "topic", "who", "achieved", "evidence", "evidence_level", "worked", "didnt_work", "relevance", "implementation", "cost", "metrics", "lesson", "region", "published")
TOPICS = ("customer_acquisition", "pricing_margins", "recruitment_staff", "operations_quality", "commercial_contracts", "recurring_revenue", "branding", "expansion",
          "franchising_acquisitions", "finance_valuation", "technology_automation", "leadership_management", "other")

EXTRACT = """You extract practical business lessons for {biz}, a small UK cleaning company (residential, end of tenancy, carpet, commercial) whose owner wants to grow into a highly profitable cleaning group.
From the SOURCE below, extract up to {n} distinct, useful lessons. Use ONLY what the source says - never add facts from memory. If the source makes a claim without evidence, mark it "claim"; personal advice is "opinion"; figures from audited/official reports are "verified"; figures reported by reputable press are "reported".
Return ONLY a JSON array. Each object: "title" (max 10 words), "topic" (one of {topics}), "who" (company/person who used it, or "General"), "achieved" (what they achieved, per the source, or ""), "evidence" (what in the source supports it, quote figures exactly), "evidence_level" (verified|reported|claim|opinion), "worked", "didnt_work" ("" if not stated), "relevance" (relevance to a small UK cleaning firm), "implementation" (how Solid Clean could apply it, concrete), "cost" (estimate, labelled as estimate, or "Unknown"), "metrics" (what to measure), "lesson" (2-3 sentence summary), "region" (UK/USA/Europe/Global/...), "published" (YYYY or YYYY-MM-DD if stated in source, else "").
If the source contains nothing useful for running or growing a cleaning business, return [].

SOURCE TYPE: {stype}
SOURCE TITLE: {title}
SOURCE URL: {url}
SOURCE TEXT:
{text}"""


class IngestIn(BaseModel):
    url: str = Field(default="", max_length=600)
    text: str = Field(default="", max_length=60000)
    title: str = Field(default="", max_length=200)
    source_type: str = "web"


class ItemPatch(BaseModel):
    status: Optional[Literal["active", "outdated", "archived"]] = None
    evidence_level: Optional[Literal["verified", "reported", "claim", "opinion"]] = None
    lesson: Optional[str] = Field(default=None, max_length=2000)
    implementation: Optional[str] = Field(default=None, max_length=2000)


def _yt_id(url: str) -> str:
    u = urlparse(url)
    if u.hostname and "youtu.be" in u.hostname:
        return u.path.strip("/")
    if u.hostname and "youtube.com" in u.hostname:
        return parse_qs(u.query).get("v", [""])[0] or (u.path.split("/")[-1] if "/shorts/" in u.path or "/live/" in u.path else "")
    return ""


def _html_text(html: str) -> tuple[str, str]:
    title = unescape((re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I) or [None, ""])[1]).strip()
    pub = (re.search(r'(?:article:modified_time|dateModified|article:published_time|datePublished)["\']?\s*(?:content=|:)\s*["\']([0-9]{4}-[0-9]{2}-[0-9]{2})', html) or [None, ""])[1]
    body = re.sub(r"<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    body = unescape(re.sub(r"<[^>]+>", " ", body))
    return title, (f"[published {pub}] " if pub else "") + re.sub(r"\s+", " ", body).strip()


async def _guard(url: str):
    host = (urlparse(url).hostname or "").lower()
    if urlparse(url).scheme not in ("http", "https") or not host:
        raise HTTPException(422, "Please enter a full web address starting with https://")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None)
    except OSError:
        raise HTTPException(422, "That web address couldn't be found.")
    if any(not ipaddress.ip_address(i[4][0]).is_global for i in infos):
        raise HTTPException(422, "That address points to a private network and can't be read.")


async def fetch_source(url: str) -> tuple[str, str, str]:
    host = (urlparse(url).hostname or "").lower()
    if any(host == b or host.endswith("." + b) for b in BLOCKED):
        raise HTTPException(422, "TikTok, Instagram, Facebook, LinkedIn and X block automated reading and require login. Copy the caption/transcript text into 'Paste text' instead.")
    await _guard(url)
    vid = _yt_id(url)
    if vid:
        from youtube_transcript_api import YouTubeTranscriptApi
        try:
            t = YouTubeTranscriptApi().fetch(vid, languages=["en", "en-GB", "en-US"])
            text = " ".join(s.text for s in t.snippets)
        except Exception as e:
            raise HTTPException(422, f"This YouTube video has no accessible English transcript ({type(e).__name__}). Paste notes or the transcript text instead.")
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            r = await c.get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json")
        meta = r.json() if r.status_code == 200 else {}
        return f"{meta.get('title', 'YouTube video')} - {meta.get('author_name', '')}".strip(" -"), text, "youtube"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False, headers={"User-Agent": "SolidCleanResearchBot/1.0 (business research; contact info@solidcleanltd.com) httpx"}) as c:
            r = await c.get(url)
            for _ in range(5):
                if not r.is_redirect:
                    break
                nxt = str(r.next_request.url)
                await _guard(nxt)
                r = await c.get(nxt)
    except httpx.HTTPError:
        raise HTTPException(502, "Couldn't reach that web page. Check the address or paste the text instead.")
    if r.status_code in (401, 402, 403):
        raise HTTPException(422, "That page is behind a login, paywall or blocks automated reading. Paste the text you're allowed to use instead.")
    if r.status_code >= 400:
        raise HTTPException(422, f"The page returned an error ({r.status_code}).")
    if "html" not in r.headers.get("content-type", "") and "text" not in r.headers.get("content-type", ""):
        raise HTTPException(422, "That link isn't a readable web page (PDFs and files aren't supported yet - paste the text instead).")
    title, text = _html_text(r.text)
    return title, text, "web"


def fingerprint(item: dict) -> str:
    key = re.sub(r"[^a-z0-9]", "", (item.get("who", "") + item.get("title", "")).lower())
    return hashlib.sha1(key.encode()).hexdigest()


def outdated(published: str) -> bool:
    return bool(re.match(r"^\d{4}", published or "")) and int(published[:4]) < now().year - 5


async def store_items(items: list, meta: dict) -> dict:
    added, dupes = [], 0
    for it in items:
        doc = {k: str(it.get(k, ""))[:1500] for k in FIELDS}
        doc["topic"] = doc["topic"] if doc["topic"] in TOPICS else "other"
        doc["evidence_level"] = doc["evidence_level"] if doc["evidence_level"] in LEVELS else "claim"
        doc["fingerprint"] = fingerprint(doc)
        if await tdb.knowledge.find_one({"fingerprint": doc["fingerprint"]}, {"_id": 1}):
            dupes += 1
            continue
        doc.update(meta, status="outdated" if outdated(doc["published"]) else "active", created_at=now_iso())
        added.append(str((await tdb.knowledge.insert_one(doc)).inserted_id))
    return {"added": len(added), "duplicates": dupes}


@router.post("/ingest")
async def ingest(body: IngestIn):
    if body.source_type not in SOURCE_TYPES:
        raise HTTPException(400, "Unknown source type")
    url = body.url.strip()
    if url and await tdb.knowledge.find_one({"source_url": url}, {"_id": 1}):
        raise HTTPException(409, "This source is already in the knowledge base.")
    if len(body.text.strip()) >= 200:
        title, text, stype = body.title or "Pasted notes", body.text.strip(), ("youtube" if _yt_id(url) else body.source_type)
    elif url:
        title, text, stype = await fetch_source(url)
        stype = stype if stype == "youtube" else body.source_type
    else:
        raise HTTPException(422, "Add a link, or paste at least a paragraph of text.")
    if len(text) < 300:
        raise HTTPException(422, "There wasn't enough readable text in that source.")
    s = await tdb.settings.find_one({}, {"business.name": 1})
    prompt = EXTRACT.format(biz=s["business"]["name"], n=6, topics="|".join(TOPICS), stype=stype, title=body.title or title, url=url or "(pasted by owner)", text=text[:30000])
    try:
        raw = await ai_complete(prompt, "Extract the lessons now.")
        items = json.loads(raw[raw.find("["): raw.rfind("]") + 1])
    except Exception:
        logger.exception("knowledge extraction failed")
        raise HTTPException(502, "The AI couldn't extract lessons from this source. Please try again.")
    meta = {"source_url": url or None, "source_title": body.title or title, "source_type": stype, "retrieved_at": now_iso(), "added_by": "owner"}
    res = await store_items(items, meta)
    await tdb.knowledge_sources.insert_one({**meta, "chars": len(text), "lessons_added": res["added"], "created_at": now_iso()})
    return {**res, "source_title": meta["source_title"]}


@router.get("")
async def list_items(q: str = "", topic: str = "", level: str = ""):
    query = {"status": {"$ne": "archived"}}
    if topic:
        query["topic"] = topic
    if level:
        query["evidence_level"] = level
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{f: rx} for f in ("title", "who", "lesson", "implementation", "source_title")]
    return outs(await tdb.knowledge.find(query).sort("created_at", -1).to_list(500))


@router.get("/stats")
async def stats():
    items = await tdb.knowledge.find({"status": {"$ne": "archived"}}, {"topic": 1, "source_type": 1, "evidence_level": 1, "status": 1, "source_url": 1, "source_title": 1}).to_list(5000)
    count = lambda k: {v: len([i for i in items if i.get(k) == v]) for v in {i.get(k) for i in items}}  # noqa: E731
    return {"lessons": len(items), "sources": len({i.get("source_url") or i.get("source_title") for i in items}), "by_topic": count("topic"),
            "by_source_type": count("source_type"), "by_evidence": count("evidence_level"), "outdated": len([i for i in items if i["status"] == "outdated"]),
            "topics": TOPICS, "source_types": SOURCE_TYPES, "live_web_research": "not connected - needs a paid search API (e.g. Perplexity) with owner approval"}


@router.patch("/{kid}")
async def patch_item(kid: str, body: ItemPatch):
    res = await tdb.knowledge.update_one({"_id": oid(kid)}, {"$set": {**body.model_dump(exclude_none=True), "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(404, "Lesson not found")
    return out(await tdb.knowledge.find_one({"_id": oid(kid)}))


@router.delete("/{kid}")
async def delete_item(kid: str):
    if not (await tdb.knowledge.delete_one({"_id": oid(kid)})).deleted_count:
        raise HTTPException(404, "Lesson not found")
    return {"ok": True}


STOP = set("the a an and or of to in for on with my our is are be how what why when which i we can should do does it this that".split())


async def relevant(question: str, n: int = 8) -> list:
    words = [w for w in re.findall(r"[a-z0-9£]+", question.lower()) if w not in STOP and len(w) > 2][:12]
    items = await tdb.knowledge.find({"status": "active"}, {"fingerprint": 0}).to_list(3000)
    def score(i):
        hay = " ".join(str(i.get(k, "")) for k in ("title", "topic", "who", "lesson", "implementation", "relevance")).lower()
        return sum(hay.count(w) for w in words) + (1 if i["evidence_level"] in ("verified", "reported") else 0)
    ranked = sorted(items, key=score, reverse=True)[:n]
    return [{k: i.get(k) for k in ("title", "who", "achieved", "evidence", "evidence_level", "worked", "didnt_work", "implementation", "cost", "metrics", "lesson", "published", "source_title", "source_url")} for i in ranked]


async def seed_knowledge():
    import pathlib
    p = pathlib.Path(__file__).with_name("knowledge_seed.json")
    if not p.exists():
        return
    for src in json.loads(p.read_text()):
        if await tdb.knowledge.find_one({"source_url": src["source_url"]}, {"_id": 1}):
            continue
        meta = {k: src[k] for k in ("source_url", "source_title", "source_type")}
        await store_items(src["lessons"], {**meta, "retrieved_at": src["retrieved_at"], "added_by": "initial_research"})

