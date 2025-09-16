from ...extensions import get_supabase
from flask import current_app

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
