import re
from html import unescape

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ai import ai_complete
from core import company_name, feature, now_iso, outs, require_admin, tdb

router = APIRouter(prefix="/api/admin/tools", dependencies=[Depends(require_admin)])


class AuditIn(BaseModel):
    url: str = Field(pattern=r"^https?://")


class BriefIn(BaseModel):
    service: str = Field(min_length=2)
    location: str = Field(min_length=2)
    kind: str = Field("seo", pattern="^(seo|ads)$")


def _tag(html: str, pattern: str) -> str:
    m = re.search(pattern, html, re.I | re.S)
    return unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""


@router.post("/seo-audit", dependencies=[Depends(feature("marketing"))])
async def seo_audit(body: AuditIn):
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers={"User-Agent": "CleanOps-SEO-Audit/1.0"}) as c:
            r = await c.get(body.url)
    except httpx.HTTPError as e:
        raise HTTPException(400, f"Could not fetch the page: {e.__class__.__name__}")
    html = r.text
    title = _tag(html, r"<title[^>]*>(.*?)</title>")
    desc = _tag(html, r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']')
    h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    imgs = re.findall(r"<img\b[^>]*>", html, re.I)
    text = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S))
    words = len(text.split())
    checks = [
        {"check": "HTTP status", "ok": r.status_code == 200, "detail": str(r.status_code)},
        {"check": "HTTPS", "ok": str(r.url).startswith("https"), "detail": str(r.url)},
        {"check": "Title tag (30-60 chars)", "ok": 30 <= len(title) <= 60, "detail": f"{len(title)} chars: {title[:80]}"},
        {"check": "Meta description (70-160 chars)", "ok": 70 <= len(desc) <= 160, "detail": f"{len(desc)} chars"},
        {"check": "Exactly one H1", "ok": len(h1s) == 1, "detail": f"{len(h1s)} found"},
        {"check": "Images have alt text", "ok": all("alt=" in i.lower() for i in imgs), "detail": f"{sum('alt=' not in i.lower() for i in imgs)} of {len(imgs)} missing"},
        {"check": "Content length (300+ words)", "ok": words >= 300, "detail": f"{words} words"},
        {"check": "Mobile viewport", "ok": 'name="viewport"' in html.lower(), "detail": ""},
        {"check": "Structured data (schema.org)", "ok": "application/ld+json" in html.lower(), "detail": ""},
        {"check": "Response time < 1.5s", "ok": r.elapsed.total_seconds() < 1.5, "detail": f"{r.elapsed.total_seconds():.2f}s"},
    ]
    score = round(sum(c["ok"] for c in checks) / len(checks) * 100)
    doc = {"type": "seo_audit", "url": str(r.url), "score": score, "checks": checks, "created_at": now_iso()}
    await tdb.marketing_runs.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.post("/brief", dependencies=[Depends(feature("marketing"))])
async def brief(body: BriefIn):
    if body.kind == "seo":
        system = ("You are a local SEO strategist for cleaning companies. Output concise markdown: 1) 12 target keywords grouped by intent "
                  "(with estimated intent, no fake search volumes), 2) a location landing page outline (title tag, meta description, H1, H2s, FAQ), "
                  "3) 4 blog post ideas, 4) 5 Google Business Profile optimisation actions. Never invent statistics or reviews.")
    else:
        system = ("You are a Google Ads specialist for cleaning companies focused on profitable bookings. Output concise markdown: 1) campaign & ad group "
                  "structure, 2) 15 keywords with match types, 3) 20 negative keywords, 4) 3 responsive search ads (headlines <=30 chars, descriptions <=90 chars), "
                  "5) geo-targeting and bidding recommendations, 6) conversion actions to track (calls, quote forms, paid bookings). No made-up claims.")
    text = await ai_complete(system, f"Company: {company_name()}. Service: {body.service}. Location: {body.location}.")
    doc = {"type": f"{body.kind}_brief", "service": body.service, "location": body.location, "content": text, "created_at": now_iso()}
    await tdb.marketing_runs.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/history")
async def history():
    return outs(await tdb.marketing_runs.find({}).sort("created_at", -1).to_list(30))
