import os
from contextvars import ContextVar
from datetime import datetime, timezone, timedelta
from typing import Annotated, Optional

import bcrypt
import jwt
from bson import ObjectId
from fastapi import HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

PyObjectId = Annotated[str, BeforeValidator(lambda v: str(v))]
JWT_ALGORITHM = "HS256"
LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
LLM_MODEL = ("anthropic", "claude-sonnet-5-5")
PAST_DUE_GRACE_DAYS = 7
current_company: ContextVar[dict] = ContextVar("current_company")
current_actor: ContextVar[str] = ContextVar("current_actor", default="system")


class BaseDocument(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    @classmethod
    def from_mongo(cls, doc):
        return cls.model_validate(doc) if doc else None

    def to_mongo(self):
        d = self.model_dump(by_alias=True)
        d.pop("_id", None)
        return d


def out(doc):
    return BaseDocument.from_mongo(doc).model_dump() if doc else None


def outs(docs):
    return [out(d) for d in docs]


def oid(value: str) -> ObjectId:
    if not ObjectId.is_valid(str(value)):
        raise HTTPException(404, "Not found")
    return ObjectId(str(value))


def now():
    return datetime.now(timezone.utc)


def now_iso():
    return now().isoformat()


def days_ago_iso(days: int):
    return (now() - timedelta(days=days)).isoformat()


class TenantCollection:
    """Mongo collection wrapper that scopes every query to the current company."""

    def __init__(self, name):
        self.c = db[name]

    @staticmethod
    def _q(q=None):
        return {**(q or {}), "company_id": current_company.get()["id"]}

    def find(self, q=None, *a, **k):
        return self.c.find(self._q(q), *a, **k)

    async def find_one(self, q=None, *a, **k):
        return await self.c.find_one(self._q(q), *a, **k)

    async def count_documents(self, q=None):
        return await self.c.count_documents(self._q(q))

    async def insert_one(self, doc):
        doc["company_id"] = current_company.get()["id"]
        return await self.c.insert_one(doc)

    async def update_one(self, q, u, **k):
        if k.get("upsert"):
            u.setdefault("$setOnInsert", {})["company_id"] = current_company.get()["id"]
        return await self.c.update_one(self._q(q), u, **k)

    async def update_many(self, q, u):
        return await self.c.update_many(self._q(q), u)

    async def delete_one(self, q):
        return await self.c.delete_one(self._q(q))

    async def delete_many(self, q):
        return await self.c.delete_many(self._q(q))


class TenantDB:
    def __getattr__(self, name):
        return TenantCollection(name)

    def __getitem__(self, name):
        return TenantCollection(name)


tdb = TenantDB()


def set_tenant(company: dict):
    current_company.set({"id": str(company["_id"]), "slug": company["slug"], "name": company["name"], "plan_key": company.get("plan_key")})


def company_name() -> str:
    return current_company.get()["name"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user_id: str, email: str, kind: str, delta: timedelta) -> str:
    payload = {"sub": user_id, "email": email, "type": kind, "exp": now() + delta}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


def decode_token(token: str, kind: str) -> dict:
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    if payload.get("type") != kind:
        raise HTTPException(401, "Invalid token type")
    return payload


def access_state(company: dict) -> dict:
    status = company.get("subscription_status")
    ok, reason = False, "Subscription inactive"
    if company.get("suspended"):
        reason = "Account suspended by the platform administrator"
    elif company.get("comped") or status == "active":
        ok = True
    elif status == "trialing":
        ok = company.get("trial_ends_at", "") > now_iso()
        reason = "Your free trial has ended"
    elif status == "past_due":
        since = company.get("past_due_since") or now_iso()
        ok = since > days_ago_iso(PAST_DUE_GRACE_DAYS)
        reason = "Payment failed - please update your payment method"
    return {"ok": ok, "reason": None if ok else reason}


async def current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    auth = request.headers.get("Authorization", "")
    if not token and auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = decode_token(token, "access")
    user = await db.users.find_one({"_id": oid(payload["sub"])}, {"password_hash": 0})
    if not user or user.get("active") is False:
        raise HTTPException(401, "User not found or deactivated")
    return user


async def require_member_any(request: Request) -> dict:
    user = await current_user(request)
    if user.get("role") not in ("owner", "staff"):
        raise HTTPException(403, "Company account required")
    company = await db.companies.find_one({"_id": oid(user["company_id"])})
    if not company:
        raise HTTPException(403, "Company not found")
    set_tenant(company)
    current_actor.set(user["email"])
    return {"user": user, "company": company}


STAFF_PATHS = ("/api/admin/bookings", "/api/admin/policies")


async def require_admin(request: Request) -> dict:
    ctx = await require_member_any(request)
    if ctx["user"]["role"] == "staff" and not request.url.path.startswith(STAFF_PATHS):
        raise HTTPException(403, "Cleaners and staff can only access their assigned jobs")
    state = access_state(ctx["company"])
    if not state["ok"]:
        raise HTTPException(402, state["reason"])
    return ctx


async def require_owner(request: Request) -> dict:
    ctx = await require_member_any(request)
    if ctx["user"]["role"] != "owner":
        raise HTTPException(403, "Only the account owner can do this")
    return ctx


async def require_platform(request: Request) -> dict:
    user = await current_user(request)
    if user.get("role") != "platform_admin":
        raise HTTPException(403, "Platform administrator only")
    return user


async def plan_features(company: dict) -> list:
    plan = await db.plans.find_one({"key": company.get("plan_key")})
    return plan.get("features", []) if plan else []


def feature(key: str):
    async def check(request: Request):
        ctx = await require_admin(request)
        if not ctx["company"].get("comped") and key not in await plan_features(ctx["company"]):
            raise HTTPException(403, f"Your plan doesn't include {key.replace('_', ' ')} - upgrade in Billing")
    return check


async def audit(action: str, detail: str):
    await tdb.audit_logs.insert_one({"action": action, "detail": detail[:2000], "actor": current_actor.get(), "at": now_iso()})


async def get_settings() -> dict:
    return await tdb.settings.find_one({}, {"_id": 0})
