import asyncio
import io
import logging
import secrets
import uuid
from datetime import timedelta

import pillow_heif
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from PIL import Image, ImageOps

from core import current_company, now, now_iso, oid, outs, require_admin, tdb
from routes_public import tenant_from_slug
from storage import APP_NAME, get_object, put_object

pillow_heif.register_heif_opener()
public = APIRouter(prefix="/api/public/{slug}/photos", dependencies=[Depends(tenant_from_slug)])
admin = APIRouter(prefix="/api/admin/bookings", dependencies=[Depends(require_admin)])
logger = logging.getLogger(__name__)
MAX_BYTES = 10 * 1024 * 1024
HOURLY_CAP = 300


def _to_jpeg(data: bytes) -> bytes:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img.thumbnail((2400, 2400))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


@public.post("")
async def upload_photo(file: UploadFile = File(...)):
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "This photo is larger than 10 MB. Please choose a smaller photo.")
    if await tdb.photos.count_documents({"created_at": {"$gte": (now() - timedelta(hours=1)).isoformat()}}) >= HOURLY_CAP:
        raise HTTPException(429, "We're receiving a lot of uploads right now. Please try again shortly.")
    try:
        jpeg = await asyncio.to_thread(_to_jpeg, data)
    except Exception:
        raise HTTPException(415, "This file isn't a supported photo. Please upload a JPG, PNG, WEBP or HEIC image.")
    path = f"{APP_NAME}/{current_company.get()['id']}/photos/{uuid.uuid4()}.jpg"
    try:
        res = await asyncio.to_thread(put_object, path, jpeg, "image/jpeg")
    except Exception:
        logger.exception("photo upload failed")
        raise HTTPException(502, "Upload failed. Please check your connection and try again.")
    token = secrets.token_urlsafe(16)
    doc = {"path": res["path"], "token": token, "status": "pending", "original_filename": (file.filename or "")[:120],
           "content_type": "image/jpeg", "size": len(jpeg), "is_deleted": False, "created_at": now_iso()}
    pid = str((await tdb.photos.insert_one(doc)).inserted_id)
    return {"id": pid, "token": token, "size": len(jpeg)}


async def _check_booking(bid: str, ctx: dict) -> dict:
    b = await tdb.bookings.find_one({"_id": oid(bid)})
    if not b or (ctx["user"]["role"] == "staff" and b.get("assigned_to") != str(ctx["user"]["_id"])):
        raise HTTPException(404, "Booking not found")
    return b


@admin.get("/{bid}/photos")
async def booking_photos(bid: str, ctx=Depends(require_admin)):
    await _check_booking(bid, ctx)
    rows = await tdb.photos.find({"booking_id": bid, "status": "attached", "is_deleted": False}, {"token": 0, "path": 0}).sort("created_at", 1).to_list(50)
    return outs(rows)


@admin.post("/{bid}/photos")
async def upload_job_photo(bid: str, kind: str = Form(...), file: UploadFile = File(...), ctx=Depends(require_admin)):
    if kind not in ("before", "after"):
        raise HTTPException(422, "Photo type must be before or after")
    b = await _check_booking(bid, ctx)
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "This photo is larger than 10 MB.")
    try:
        jpeg = await asyncio.to_thread(_to_jpeg, data)
    except Exception:
        raise HTTPException(415, "This file isn't a supported photo.")
    res = await asyncio.to_thread(put_object, f"{APP_NAME}/{current_company.get()['id']}/jobs/{uuid.uuid4()}.jpg", jpeg, "image/jpeg")
    doc = {"path": res["path"], "status": "attached", "kind": kind, "booking_id": bid, "lead_id": b.get("lead_id"), "uploaded_by": ctx["user"].get("name") or ctx["user"]["email"],
           "content_type": "image/jpeg", "size": len(jpeg), "is_deleted": False, "created_at": now_iso(), "attached_at": now_iso()}
    return {"id": str((await tdb.photos.insert_one(doc)).inserted_id)}


@admin.get("/photos/{pid}/file")
async def photo_file(pid: str, ctx=Depends(require_admin)):
    p = await tdb.photos.find_one({"_id": oid(pid), "status": "attached", "is_deleted": False})
    if not p:
        raise HTTPException(404, "Photo not found")
    if ctx["user"]["role"] == "staff":
        if not p.get("booking_id"):
            raise HTTPException(404, "Photo not found")
        await _check_booking(p["booking_id"], ctx)
    data = await asyncio.to_thread(get_object, p["path"])
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})
