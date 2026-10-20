from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import asyncio
import logging
import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

import routes_admin
import routes_auth
import routes_chat
import routes_growth
import routes_policies
import routes_public
import routes_saas
import routes_tools
import routes_voice
import routes_photos
import routes_walkthrough
import routes_carpet
import routes_recurring
import routes_finance
import routes_manager
import storage
from automations import run_all_companies
from core import client
from seed import seed_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="CleanOps")
for r in (routes_auth.router, routes_saas.router, routes_saas.platform, routes_public.router, routes_public.public, routes_chat.router,
          routes_admin.router, routes_growth.router, routes_growth.outreach, routes_growth.reviews_r, routes_tools.router, routes_policies.router, routes_voice.router, routes_voice.admin, routes_photos.public, routes_photos.admin, routes_walkthrough.public, routes_walkthrough.admin, routes_carpet.public, routes_carpet.admin, routes_recurring.cron, routes_recurring.admin, routes_finance.router, routes_manager.router):
    app.include_router(r)

HITS = defaultdict(deque)
LIMITS = (("/api/auth/", 60), ("/api/public/", 180))


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    path = request.url.path
    limit = next((n for p, n in LIMITS if path.startswith(p)), None)
    if limit:
        ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "x")).split(",")[0].strip()
        q, t = HITS[(ip, path.split("/")[2])], time.monotonic()
        while q and t - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            return JSONResponse({"detail": "Too many requests - please wait a minute and try again."}, status_code=429)
        q.append(t)
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ["CORS_ORIGINS"].split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


async def automation_loop():
    while True:
        try:
            logger.info("automations ran for %s companies", await run_all_companies())
        except Exception:
            logger.exception("automation run failed")
        await asyncio.sleep(1800)


@app.on_event("startup")
async def startup():
    await seed_all()
    try:
        await asyncio.to_thread(storage.init_storage)
    except Exception:
        logger.exception("Storage init failed")
    asyncio.create_task(routes_saas.seed_plans())
    asyncio.create_task(automation_loop())


@app.on_event("shutdown")
async def shutdown():
    client.close()
