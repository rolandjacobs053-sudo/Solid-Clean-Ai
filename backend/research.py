import asyncio
import logging
import os
from datetime import timedelta

import httpx
from fastapi import HTTPException

from core import now, now_iso, tdb

logger = logging.getLogger(__name__)
WEEKLY_CAP = 20
TOPICS = [
    "How UK cleaning companies win and keep commercial office cleaning contracts - recent examples and tender tactics",
    "UK domestic and end of tenancy cleaning prices, labour costs and profit margins this year",
    "How UK cleaning businesses recruit, train and retain reliable cleaners - pay rates, vetting, retention tactics",
    "Cleaning company franchising and acquisitions in the UK and USA - recent deals, valuation multiples and lessons",
    "UK contract cleaning market size, growth and trends - latest industry reports",
    "Partnerships with letting agents, landlords and property managers for end of tenancy cleaning in the UK",
    "Local SEO, Google Business Profile and Local Services Ads results for cleaning companies",
    "How cleaning companies use automation, scheduling software and AI to cut admin and scale",
]


def perplexity() -> bool:
    return bool(os.environ.get("PERPLEXITY_API_KEY"))


def connected() -> bool:
    return True


def provider() -> str:
    return "Perplexity" if perplexity() else "Free web search"


async def used_this_week() -> int:
    return await tdb.research_log.count_documents({"created_at": {"$gte": (now() - timedelta(days=7)).isoformat()}})


async def status() -> dict:
    used = await used_this_week()
    return {"provider": provider(), "connected": connected(), "weekly_cap": WEEKLY_CAP, "used_this_week": used, "remaining": max(0, WEEKLY_CAP - used), "topics": TOPICS,
            "last": [{k: r.get(k) for k in ("query", "created_at", "sources_count", "trigger")} for r in await tdb.research_log.find({}).sort("created_at", -1).to_list(10)]}


def _parse(raw: dict) -> tuple[str, list]:
    text = raw.get("output_text") or ""
    if not text:
        for item in raw.get("output") or []:
            for c in item.get("content") or []:
                text += c.get("text") or ""
    if not text:
        text = ((raw.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    sources = [{"url": s.get("url"), "title": s.get("title") or s.get("url"), "date": s.get("date") or s.get("last_updated")} for s in raw.get("search_results") or [] if s.get("url")]
    for u in raw.get("citations") or []:
        u = u if isinstance(u, str) else u.get("url")
        if u and u not in [s["url"] for s in sources]:
            sources.append({"url": u, "title": u, "date": None})
    return text.strip(), sources[:12]


FREE_SYSTEM = ("You are a research analyst. Using ONLY the numbered web results provided, write a factual briefing that answers the question. "
               "Cite every fact as [n]. Give specific figures, dates and named companies where the sources have them. "
               "Say clearly when sources disagree, are thin, or are just a company's own marketing claims. Never invent facts or sources.")


async def _free(query: str, prompt: str) -> tuple[str, list]:
    from ddgs import DDGS
    from ai import ai_complete
    from routes_knowledge import fetch_source
    try:
        hits = await asyncio.to_thread(lambda: DDGS().text(query[:250], region="uk-en", max_results=8))
    except Exception:
        logger.warning("free search failed", exc_info=True)
        raise HTTPException(502, "The web search didn't respond. Please try again in a minute.")
    hits = [h for h in hits or [] if h.get("href")]
    if not hits:
        raise HTTPException(502, "The web search found nothing for that question - try rewording it.")

    async def page(h):
        try:
            return (await asyncio.wait_for(fetch_source(h["href"]), 20))[1][:3000]
        except Exception:
            return ""
    pages = await asyncio.gather(*[page(h) for h in hits[:4]])
    sources = [{"url": h["href"], "title": h.get("title") or h["href"], "date": None} for h in hits]
    blocks = "\n\n".join(f"[{i + 1}] {h.get('title')} - {h['href']}\nSnippet: {h.get('body', '')}" + (f"\nPage text: {pages[i]}" if i < len(pages) and pages[i] else "")
                         for i, h in enumerate(hits))
    text = await ai_complete(FREE_SYSTEM, f"QUESTION: {prompt}\n\nWEB RESULTS:\n{blocks}")
    return text, sources


async def web_research(query: str, trigger: str) -> dict:
    if await used_this_week() >= WEEKLY_CAP:
        raise HTTPException(429, f"This week's research limit ({WEEKLY_CAP} searches) has been reached, to keep costs under control.")
    prompt = (f"{query}\n\nFocus on credible, recent sources (official reports, company filings, reputable press, industry bodies). "
              "Give specific facts with figures and dates, name the companies/people involved, and say when evidence is weak or a claim is unverified.")
    if not perplexity():
        text, sources = await _free(query, prompt)
        await tdb.research_log.insert_one({"query": query[:300], "trigger": trigger, "sources_count": len(sources), "provider": "free", "created_at": now_iso()})
        return {"answer": text, "sources": sources}
    headers = {"Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(base_url="https://api.perplexity.ai", timeout=httpx.Timeout(90, connect=10), headers=headers) as c:
            r = await c.post("/v1/agent", json={"preset": "fast", "input": prompt})
            if r.status_code in (400, 404):
                r = await c.post("/v1/sonar", json={"model": "sonar", "messages": [{"role": "user", "content": prompt}], "web_search_options": {"search_context_size": "low"}})
    except httpx.HTTPError:
        raise HTTPException(502, "Couldn't reach Perplexity. Please try again.")
    if r.status_code in (401, 403):
        raise HTTPException(502, "Perplexity rejected the API key - check it's correct and has credit.")
    if r.status_code == 429:
        raise HTTPException(503, "Perplexity is busy or your Perplexity credit/rate limit is reached. Try again later.")
    if r.status_code >= 400:
        logger.warning("perplexity error %s", r.status_code)
        raise HTTPException(502, "Perplexity couldn't complete the search.")
    text, sources = _parse(r.json())
    await tdb.research_log.insert_one({"query": query[:300], "trigger": trigger, "sources_count": len(sources), "created_at": now_iso()})
    return {"answer": text, "sources": sources}
