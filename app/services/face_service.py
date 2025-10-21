# flask_api_face/app/services/face_service.py

from __future__ import annotations

import io
import time
import logging
from typing import List, Union

import numpy as np
import cv2
from werkzeug.datastructures import FileStorage

from ..extensions import get_face_engine, celery
from .storage.supabase_storage import upload_bytes, signed_url, download, list_objects
from ..db import get_session
from ..db.models import User
from .notification_service import send_notification


logger = logging.getLogger(__name__)


# -------------
# Util kecil
# -------------
def _now_ts() -> int:
    return int(time.time())


def _normalize(v: np.ndarray, eps: float = 1e-10) -> np.ndarray:
    n = np.linalg.norm(v) + eps
    return v / n


def _score(a: np.ndarray, b: np.ndarray, metric: str = "cosine") -> float:
    if metric == "cosine":
        return float(np.dot(a, b))
    elif metric == "l2":
        return float(-np.linalg.norm(a - b))
    else:
        raise ValueError(f"Unsupported metric: {metric}")


def _is_match(score: float, metric: str, threshold: float) -> bool:
    # cosine: lebih besar lebih mirip; l2: lebih besar (negatif kecil) berarti lebih mirip
    if metric == "cosine":
        return score >= threshold
    elif metric == "l2":
        return score >= -threshold
    else:
        return False


def decode_image(file_or_bytes: Union[FileStorage, bytes, bytearray, np.ndarray]) -> np.ndarray:
    """Terima FileStorage (Flask upload), bytes (dari Supabase), atau ndarray.
    Return BGR ndarray untuk konsumsi OpenCV/insightface.
    """
    if isinstance(file_or_bytes, np.ndarray):
        img = file_or_bytes
    elif isinstance(file_or_bytes, (bytes, bytearray)):
        img = cv2.imdecode(np.frombuffer(file_or_bytes, np.uint8), cv2.IMREAD_COLOR)
    elif isinstance(file_or_bytes, FileStorage):
        data = file_or_bytes.read()
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    else:
        raise TypeError(f"Tipe tidak didukung untuk decode_image: {type(file_or_bytes)}")

    if img is None:
        raise ValueError("Gagal decode gambar (hasil None).")
    return img


def get_embedding(img: np.ndarray) -> np.ndarray | None:
    """Ambil embedding wajah pertama yang terdeteksi. Return None jika tidak ada wajah."""
    # Pastikan engine ada; lazy init akan berjalan bila belum ada.
    engine = get_face_engine()
    faces = engine.get(img)  # insightface.FaceAnalysis
    if not faces:
        return None
    # Ambil wajah terbesar / yang pertama
    face = max(faces, key=lambda f: f.bbox[2] * f.bbox[3] if hasattr(f, "bbox") else 0)
    return face.embedding


def _user_root(user_id: str) -> str:
    user_id = (user_id or "").strip()
    if not user_id:
        raise ValueError("user_id kosong")
    return f"face_detection/{user_id}"


@celery.task(name="tasks.enroll_user_task")
def enroll_user_task(user_id: str, user_name: str, images_data: List[bytes]):
    """
    Enroll wajah user berdasarkan beberapa gambar (list bytes),
    disimpan baseline + embedding rata-rata ke Supabase storage.
    """
    logger.info(f"Memulai proses enroll wajah untuk user_id: {user_id}")

    try:
        embeddings = []
        uploaded = []

        for idx, img_bytes in enumerate(images_data, 1):
            logger.info(f"Memproses gambar #{idx} untuk user {user_id}")
            img = decode_image(img_bytes)

            emb = get_embedding(img)  # <-- akan lazy init engine bila perlu
            if emb is None:
                logger.warning(f"Wajah tidak terdeteksi pada gambar #{idx} untuk user {user_id}")
                continue

            emb = _normalize(emb.astype(np.float32))

            # Simpan baseline image
            ok, buf = cv2.imencode(".jpg", img)
            if not ok:
                logger.warning(f"Gagal encode JPEG untuk gambar #{idx}")
                continue
            ts = _now_ts()
            key = f"{_user_root(user_id)}/baseline_{ts}_{idx}.jpg"
            upload_bytes(key, buf.tobytes(), "image/jpeg")
            uploaded.append({"path": key})
            embeddings.append(emb)
            logger.info(f"Gambar #{idx} berhasil diunggah ke {key}")

        if not embeddings:
            logger.error(f"Pendaftaran wajah gagal untuk user {user_id}: Tidak ada wajah terdeteksi.")
            return {"status": "error", "message": "Tidak ada wajah yang terdeteksi di semua gambar."}

        mean_emb = _normalize(np.stack(embeddings, axis=0).mean(axis=0))
        emb_io = io.BytesIO()
        np.save(emb_io, mean_emb)
        emb_key = f"{_user_root(user_id)}/embedding.npy"
        upload_bytes(emb_key, emb_io.getvalue(), "application/octet-stream")
        logger.info(f"Embedding berhasil disimpan di {emb_key}")

        # Kirim notifikasi sukses
        try:
            with get_session() as s:
                send_notification(
                    event_trigger="FACE_REGISTRATION_SUCCESS",
                    user_id=user_id,
                    dynamic_data={"nama_karyawan": user_name},
                    session=s,
                )
                logger.info(f"Notifikasi sukses dikirim ke user {user_id}")
        except Exception as e:
            logger.warning(f"Gagal mengirim notifikasi sukses: {e}", exc_info=True)

        return {
            "status": "success",
            "user_id": user_id,
            "images_count": len(uploaded),
            "embedding_path": emb_key,
        }

    except Exception as e:
        # Penting: tulis stacktrace agar akar masalah jelas (mis. init engine gagal)
        logger.error(f"Error dalam enroll_user_task untuk user {user_id}: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


def verify_user(
    user_id: str,
    probe_file: Union[FileStorage, bytes, bytearray, np.ndarray],
    metric: str = "cosine",
    threshold: float = 0.45,
):
    """Verifikasi wajah terhadap embedding/baseline yang disimpan."""
    probe_img = decode_image(probe_file)
    probe_emb = get_embedding(probe_img)
    if probe_emb is None:
        raise RuntimeError("Tidak ada wajah terdeteksi di probe image.")
    probe_n = _normalize(probe_emb.astype(np.float32))

    emb_key = f"{_user_root(user_id)}/embedding.npy"

    ref = None
    try:
        emb_bytes = download(emb_key)
        ref = np.load(io.BytesIO(emb_bytes))
    except Exception:
        ref = None

    if ref is None:
        # fallback: rata-rata 3 baseline pertama
        items = list_objects(f"{_user_root(user_id)}")
        baselines = [it for it in items if it.get("name", "").startswith("baseline_")]
        if not baselines:
            raise FileNotFoundError("Embedding & baseline user belum ada di storage")
        embs = []
        for it in baselines[:3]:
            data = download(it["path"])
            img = decode_image(data)
            emb = get_embedding(img)
            if emb is not None:
                embs.append(_normalize(emb.astype(np.float32)))
        if not embs:
            raise RuntimeError("Gagal hitung embedding baseline")
        ref = np.stack(embs, axis=0).mean(axis=0)

    ref_n = _normalize(ref.astype(np.float32))
    score = _score(ref_n, probe_n, metric)
    match = _is_match(score, metric, threshold)

    return {
        "user_id": user_id,
        "metric": metric,
        "threshold": threshold,
        "score": float(score),
        "match": bool(match),
    }
