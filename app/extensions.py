# flask_api_face/app/extensions.py

from __future__ import annotations

import os
import json
from typing import Optional
import logging
from insightface.app import FaceAnalysis

from flask import Flask, current_app
from flask_cors import CORS
from celery import Celery, Task

from supabase import create_client, Client
import firebase_admin
from firebase_admin import credentials

# --- Windows + multiprocessing quirk ---
if os.name == "nt":
    os.environ.setdefault("FORKED_BY_MULTIPROCESSING", "1")

# --- Globals ---
celery: Celery = Celery(__name__)
_face_engine: Optional[FaceAnalysis] = None # <-- Kita hanya akan pakai variabel ini
_supabase: Optional[Client] = None
_firebase_app: Optional[firebase_admin.App] = None
log = logging.getLogger(__name__)

# -------------------------
# Celery <-> Flask binding
# -------------------------
class FlaskContextTask(Task):
    """
    Memastikan setiap task berjalan di dalam Flask app_context.
    Gunakan atribut 'flask_app' agar tidak bentrok dengan Task.app (Celery app).
    """
    flask_app: Optional[Flask] = None

    def __call__(self, *args, **kwargs):
        app_obj = getattr(self, "flask_app", None)
        if app_obj is None:
            try:
                app_obj = current_app._get_current_object()
            except Exception:
                app_obj = None

        if app_obj is not None:
            with app_obj.app_context():
                return self.run(*args, **kwargs)
        return self.run(*args, **kwargs)


def init_celery(app: Flask) -> None:
    """Konfigurasi Celery dan pasang Task base yang membawa app_context Flask."""
    broker = app.config.get("CELERY_BROKER_URL")
    backend = app.config.get("CELERY_RESULT_BACKEND")

    celery.conf.update(
        broker_url=broker,
        result_backend=backend,
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone=app.config.get("TIMEZONE", "UTC"),
        enable_utc=False,
    )

    celery.Task = FlaskContextTask
    FlaskContextTask.flask_app = app


# -------------------------
# Face engine (insightface)
# -------------------------
def init_face_engine(app=None):
    """
    Inisialisasi global face_engine sekali saja.
    Argumen 'app' opsional agar kompatibel dengan pemanggilan lama/baru.
    """
    global _face_engine  # <-- DIUBAH: Menggunakan _face_engine
    if _face_engine is not None:
        return _face_engine

    try:
        providers = ["CPUExecutionProvider"]
        model_name = "buffalo_s"
        det_size = (640, 640)

        engine = FaceAnalysis(name=model_name, providers=providers)
        engine.prepare(ctx_id=0, det_size=det_size)

        _face_engine = engine  # <-- DIUBAH: Menyimpan ke _face_engine
        log.info("InsightFace initialized: name=%s providers=%s", model_name, providers)
        return _face_engine
    except Exception as e:
        log.warning("InsightFace init failed: %s", e)
        return None

def get_face_engine() -> FaceAnalysis:
    """Lazy getter: kalau belum ada, coba init dari current_app."""
    global _face_engine
    if _face_engine is None:
        try:
            app = current_app._get_current_object()
        except Exception:
            app = None

        if app is not None:
            init_face_engine(app)

    if _face_engine is None:
        raise RuntimeError("Face recognition engine not initialized. "
                           "Pastikan worker Celery memanggil init_face_engine() "
                           "atau jalankan task dalam konteks Flask dengan init_celery().")
    return _face_engine


# -------------------------
# Supabase
# -------------------------
def init_supabase(app: Flask) -> None:
    global _supabase
    if _supabase is not None:
        return

    url = app.config.get("SUPABASE_URL")
    key = app.config.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        app.logger.warning("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY tidak di-set.")
        return

    try:
        _supabase = create_client(url, key)
        app.logger.info("Supabase client initialized.")
    except Exception as e:
        _supabase = None
        app.logger.error(f"Gagal inisialisasi Supabase: {e}", exc_info=True)


def get_supabase() -> Optional[Client]:
    return _supabase


# -------------------------
# Firebase Admin
# -------------------------
def init_firebase(app: Flask) -> None:
    """Inisialisasi Firebase Admin dari variabel lingkungan."""
    global _firebase_app
    if _firebase_app is not None or firebase_admin._apps:
        return

    cred = None
    try:
        # Prioritas 1: Menggunakan variabel lingkungan terpisah dari app.config
        project_id = app.config.get('FIREBASE_PROJECT_ID')
        client_email = app.config.get('FIREBASE_CLIENT_EMAIL')
        private_key = app.config.get('FIREBASE_PRIVATE_KEY')

        # === LOGGING UNTUK DEBUGGING ===
        log.info(f"Firebase Init Check: project_id is {'present' if project_id else 'missing'}")
        log.info(f"Firebase Init Check: client_email is {'present' if client_email else 'missing'}")
        log.info(f"Firebase Init Check: private_key is {'present' if private_key else 'missing'}")
        # ===============================

        if all([project_id, client_email, private_key]):
            private_key_formatted = private_key.replace('\\n', '\n')
            cred_dict = {
                "type": "service_account",
                "project_id": project_id,
                "private_key": private_key_formatted,
                "client_email": client_email,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            cred = credentials.Certificate(cred_dict)
            app.logger.info("Memuat kredensial Firebase dari variabel lingkungan.")
        else:
            app.logger.warning("Satu atau lebih variabel lingkungan Firebase (PROJECT_ID, CLIENT_EMAIL, PRIVATE_KEY) tidak ditemukan di app.config.")

        # Inisialisasi aplikasi jika kredensial berhasil didapatkan
        if cred:
            _firebase_app = firebase_admin.initialize_app(cred)
            app.logger.info("Firebase Admin SDK initialized.")
        else:
            app.logger.warning("No valid Firebase credentials found; Firebase not initialized.")

    except Exception as e:
        app.logger.error(f"Error initializing Firebase Admin SDK: {e}", exc_info=True)


# -------------------------
# Flask app wiring
# -------------------------
def init_app(app: Flask) -> None:
    """Dipanggil dari create_app()."""
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    init_celery(app)
    init_supabase(app)
    try:
        init_firebase(app)
    except Exception:
        app.logger.exception("Firebase init failed during app init.")