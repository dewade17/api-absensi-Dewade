import io
import time
import numpy as np
import cv2

from ..extensions import get_face_engine
from .storage.supabase_storage import upload_bytes, signed_url, download, list_objects


def _now_ts() -> int:
    return int(time.time())


def _today_str() -> str:
    import datetime as _dt
    return _dt.datetime.utcnow().strftime("%Y%m%d")


def _normalize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    n = np.linalg.norm(x) + eps
    return x / n


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = _normalize(a)
    b = _normalize(b)
    return float(np.dot(a, b))


def _l2(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def _score(a: np.ndarray, b: np.ndarray, metric: str) -> float:
    return _cosine(a, b) if metric == "cosine" else _l2(a, b)


def _is_match(score: float, metric: str, threshold: float) -> bool:
    return score >= threshold if metric == "cosine" else score <= threshold


def decode_image(file_storage):
    data = file_storage.read()
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Invalid image")
    return img


def get_embedding(img_bgr):
    engine = get_face_engine()
    faces = engine.get(img_bgr)
    if not faces:
        return None
    return faces[0].embedding


# -------- path helpers: face_detection/<id_user> --------
def _user_root(user_id: str) -> str:
    """
    Gunakan id_user sebagai nama folder, tanpa membaca nama_pengguna.
    Contoh: face_detection/6c7d7e2a-f2c1-4b9a-9a0b-9f2a6c1d2e3f
    """
    user_id = (user_id or "").strip()
    if not user_id:
        raise ValueError("user_id kosong")
    return f"face_detection/{user_id}"


# -------- public services --------
def enroll_user(user_id: str, images):
    embeddings = []
    uploaded = []

    for idx, f in enumerate(images, 1):
        # pastikan pointer stream di awal (untuk objek seperti Werkzeug FileStorage)
        if hasattr(f, "stream") and hasattr(f.stream, "seek"):
            f.stream.seek(0)

        img = decode_image(f)
        emb = get_embedding(img)
        if emb is None:
            raise ValueError(f"Wajah tidak terdeteksi pada gambar #{idx}")
        emb = _normalize(emb.astype(np.float32))

        _, buf = cv2.imencode(".jpg", img)
        ts = _now_ts()
        key = f"{_user_root(user_id)}/baseline_{ts}_{idx}.jpg"
        upload_bytes(key, buf.tobytes(), "image/jpeg")
        uploaded.append({"path": key, "signed_url": signed_url(key)})
        embeddings.append(emb)

    mean_emb = _normalize(np.stack(embeddings, axis=0).mean(axis=0))
    emb_io = io.BytesIO()
    np.save(emb_io, mean_emb)
    emb_key = f"{_user_root(user_id)}/embedding.npy"
    upload_bytes(emb_key, emb_io.getvalue(), "application/octet-stream")

    return {
        "user_id": user_id,
        "images": uploaded,
        "embedding_path": emb_key,
        "embedding_signed_url": signed_url(emb_key),
        "shots": len(uploaded),
    }


def verify_user(
    user_id: str,
    probe_file,
    metric: str = "cosine",
    threshold: float = 0.45,
):
    probe_img = decode_image(probe_file)
    probe_emb = get_embedding(probe_img)
    if probe_emb is None:
        raise ValueError("Wajah tidak terdeteksi pada probe")
    probe_n = _normalize(probe_emb.astype(np.float32))

    emb_key = f"{_user_root(user_id)}/embedding.npy"
    ref = None
    try:
        emb_bytes = download(emb_key)
        ref = np.load(io.BytesIO(emb_bytes))
    except Exception:
        ref = None

    if ref is None:
        prefix = f"{_user_root(user_id)}"
        items = list_objects(prefix)
        baselines = [it for it in items if it.get("name", "").startswith("baseline_")]
        if not baselines:
            raise FileNotFoundError("Embedding & baseline user belum ada di storage")
        embs = []
        for it in baselines[:3]:
            key = f"{prefix}/{it['name']}"
            img_bytes = download(key)
            img_arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
            e = get_embedding(img)
            if e is not None:
                embs.append(_normalize(e.astype(np.float32)))
        if not embs:
            raise RuntimeError("Gagal hitung embedding baseline")
        ref = np.stack(embs, axis=0).mean(axis=0)

    ref_n = _normalize(ref.astype(np.float32))
    score = _score(ref_n, probe_n, metric)
    match = _is_match(score, metric, threshold)

    # Tidak menyimpan probe image atau metadata saat verifikasi (sesuai permintaan).
    return {
        "user_id": user_id,
        "metric": metric,
        "threshold": threshold,
        "score": float(score),
        "match": bool(match),
    }
