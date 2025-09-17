from ...extensions import get_supabase
from flask import current_app
import os
import re
from datetime import datetime
from uuid import uuid4

def upload_bytes(path: str, data: bytes, content_type: str) -> str:
    sb = get_supabase()
    assert sb is not None, "Supabase not configured"
    sb.storage.from_(current_app.config["SUPABASE_BUCKET"]).upload(path, data, {
        "content-type": content_type,
        "x-upsert": "true"
    })
    return path

def signed_url(path: str, expires_in: int = None) -> str:
    sb = get_supabase()
    assert sb is not None, "Supabase not configured"
    if expires_in is None:
        expires_in = current_app.config["SIGNED_URL_EXPIRES"]
    res = sb.storage.from_(current_app.config["SUPABASE_BUCKET"]).create_signed_url(path, expires_in)
    return res["signedURL"] if isinstance(res, dict) and "signedURL" in res else str(res)

def download(path: str) -> bytes:
    sb = get_supabase()
    assert sb is not None, "Supabase not configured"
    return sb.storage.from_(current_app.config["SUPABASE_BUCKET"]).download(path)

def list_objects(prefix: str):
    sb = get_supabase()
    assert sb is not None, "Supabase not configured"
    return sb.storage.from_(current_app.config["SUPABASE_BUCKET"]).list(path=prefix)

def _sanitize_filename(filename: str) -> str:
    """Sanitize filename keeping extension, ensure safe value."""
    if not filename:
        base, ext = "file", ""
    else:
        base, ext = os.path.splitext(filename)
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base).strip("._") or "file"
    ext = re.sub(r"[^A-Za-z0-9.]", "", ext)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    suffix = uuid4().hex[:8]
    return f"{base}_{timestamp}_{suffix}{ext.lower()}"


def build_catatan_path(user_id: str, filename: str) -> str:
    """Return storage path for catatan attachments under lampiran-catatan/<user_id>/"""
    user_part = (user_id or "unknown").strip() or "unknown"
    safe_filename = _sanitize_filename(filename)
    return f"lampiran-catatan/{user_part}/{safe_filename}"