from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import asyncio
import logging
import os

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

import routes_admin
import routes_auth
import routes_chat
import routes_growth
import routes_public
import routes_saas
import routes_tools
from automations import run_all_companies
from core import client
from seed import seed_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="CleanOps")
for r in (routes_auth.router, routes_saas.router, routes_saas.platform, routes_public.router, routes_public.public, routes_chat.router,
          routes_admin.router, routes_growth.router, routes_growth.outreach, routes_growth.reviews_r, routes_tools.router):
    app.include_router(r)

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
    asyncio.create_task(routes_saas.seed_plans())
    asyncio.create_task(automation_loop())


@app.on_event("shutdown")
async def shutdown():
    client.close()
