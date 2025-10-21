# flask_api_face/app/blueprints/face/routes.py

from __future__ import annotations

from flask import Blueprint, request, current_app
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...utils.responses import ok, error
from ...services.face_service import verify_user, enroll_user_task
from ...services.storage.supabase_storage import list_objects, signed_url
from ...db import get_session
from ...db.models import Device, User
from ...utils.timez import now_local

# Blueprint TANPA prefix di sini; prefix ditaruh saat register_blueprint di create_app()
face_bp = Blueprint("face", __name__)

@face_bp.post("/enroll")
def enroll():
    """Daftarkan wajah pengguna (enqueue Celery) + catat/perbarui perangkat."""
    current_app.logger.info("Menerima permintaan baru di POST /api/face/enroll")

    # --- Ambil field dari form-data ---
    user_id = (request.form.get("user_id") or "").strip()
    device_label = (request.form.get("device_label") or "").strip()
    device_identifier = (request.form.get("device_identifier") or "").strip()
    platform = (request.form.get("platform") or "").strip()  # android/ios/web
    os_version = (request.form.get("os_version") or "").strip()
    app_version = (request.form.get("app_version") or "").strip()
    fcm_token = (request.form.get("fcm_token") or "").strip()

    # Kumpulan file gambar (bisa multiple 'images')
    files = request.files.getlist("images") or []
    if not user_id:
        return error("user_id wajib ada", 400)
    if not files:
        return error("Minimal unggah 1 file 'images'", 400)

    # --- Decode file menjadi bytes untuk dikirim ke Celery ---
    images_data = []
    for i, f in enumerate(files, 1):
        data = f.read()
        if not data:
            current_app.logger.warning(f"Gambar #{i} kosong; dilewati")
            continue
        images_data.append(data)

    if not images_data:
        return error("Semua file 'images' kosong/invalid", 400)

    try:
        with get_session() as s:
            # Validasi user
            user = s.execute(select(User).where(User.id_user == user_id)).scalar_one_or_none()
            if user is None:
                return error(f"User dengan id_user '{user_id}' tidak ditemukan.", 404)

            user_name = user.nama_pengguna or "User"

            # Enqueue task Celery (non-blocking)
            enroll_user_task.delay(user_id, user_name, images_data)

            # Catat / update device
            now_naive_utc = now_local().replace(tzinfo=None)
            device = None
            if device_identifier:
                device = s.execute(
                    select(Device).where(
                        Device.id_user == user_id,
                        Device.device_identifier == device_identifier
                    )
                ).scalar_one_or_none()

            if device is None:
                device = Device(
                    id_user=user_id,
                    device_label=device_label or None,
                    platform=platform or None,
                    os_version=os_version or None,
                    app_version=app_version or None,
                    device_identifier=device_identifier or None,
                    last_seen=now_naive_utc,
                    fcm_token=fcm_token or None,
                    fcm_token_updated_at=now_naive_utc if fcm_token else None
                )
                s.add(device)
            else:
                device.device_label = device_label or device.device_label
                device.platform = platform or device.platform
                device.os_version = os_version or device.os_version
                device.app_version = app_version or device.app_version
                device.last_seen = now_naive_utc
                if fcm_token and fcm_token != (device.fcm_token or ""):
                    device.fcm_token = fcm_token
                    device.fcm_token_updated_at = now_naive_utc

            try:
                s.commit()
            except IntegrityError as e:
                s.rollback()
                current_app.logger.warning(f"Gagal menyimpan device untuk user {user_id}: {e}")

        # Respon cepat; proses heavy dikerjakan Celery
        return ok(message="Registrasi wajah berhasil di proses sistem", user_id=user_id, images=len(images_data))

    except Exception as e:
        current_app.logger.error(f"Kesalahan tidak terduga pada endpoint enroll: {e}", exc_info=True)
        return error(str(e), 500)

@face_bp.post("/verify")
def verify():
    """Verifikasi wajah (sinkron, cepat)."""
    user_id = (request.form.get("user_id") or "").strip()
    metric = (request.form.get("metric") or "cosine").strip()
    threshold = float(request.form.get("threshold") or 0.45)
    f = request.files.get("image")

    if not user_id:
        return error("user_id wajib ada", 400)
    if f is None:
        return error("Field 'image' wajib ada", 400)

    try:
        data = verify_user(user_id, f, metric=metric, threshold=threshold)
        return ok(**data)
    except FileNotFoundError as e:
        return error(str(e), 404)
    except Exception as e:
        current_app.logger.error(f"Kesalahan di verify: {e}", exc_info=True)
        return error(str(e), 500)

@face_bp.get("/<user_id>")
def get_face_data(user_id: str):
    """List file baseline & embedding user (signed URLs)."""
    if not user_id:
        return error("user_id wajib ada", 400)

    prefix = f"face_detection/{user_id}"
    try:
        items = list_objects(prefix)
        files = []
        for it in items:
            name = it.get("name") or it.get("path") or ""
            path = f"{prefix}/{name}" if not name.startswith(prefix) else name
            url = signed_url(path)
            files.append({"name": name.split("/")[-1], "path": path, "signed_url": url})

        return ok(user_id=user_id, prefix=prefix, count=len(files), items=files)
    except Exception as e:
        current_app.logger.error(f"Kesalahan tidak terduga pada endpoint get_face_data: {e}", exc_info=True)
        return error(str(e), 500)
