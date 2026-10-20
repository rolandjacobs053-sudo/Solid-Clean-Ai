import os

import requests
from bson import ObjectId

from core import now_iso, tdb

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ["EMERGENT_LLM_KEY"]
APP_NAME = "solidclean"
storage_key = None


def init_storage(force: bool = False):
    global storage_key
    if storage_key and not force:
        return storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key


def _call(method: str, path: str, **kw):
    for attempt in (0, 1):
        resp = requests.request(method, f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": init_storage(force=attempt == 1), **kw.pop("headers", {})}, **kw)
        if resp.status_code != 404 or attempt:
            resp.raise_for_status()
            return resp


def put_object(path: str, data: bytes, content_type: str) -> dict:
    return _call("PUT", path, headers={"Content-Type": content_type}, data=data, timeout=120).json()


def get_object(path: str) -> bytes:
    return _call("GET", path, timeout=60).content


async def attach_photos(refs, **link) -> int:
    count = 0
    for r in refs[:10]:
        if not ObjectId.is_valid(r.id):
            continue
        res = await tdb.photos.update_one({"_id": ObjectId(r.id), "token": r.token, "status": "pending"},
                                          {"$set": {"status": "attached", "attached_at": now_iso(), **link}})
        count += res.modified_count
    return count
