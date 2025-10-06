from flask import Blueprint, request, current_app
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...utils.responses import ok, error
from ...services.face_service import enroll_user, verify_user
from ...services.storage.supabase_storage import list_objects, signed_url
from ...services.notification_service import send_notification  # <-- 1. Impor layanan notifikasi
from ...db import get_session
from ...db.models import Device, User
from ...utils.timez import now_local

face_bp = Blueprint("face", __name__)


@face_bp.post("/enroll")
def enroll():
    user_id = (request.form.get("user_id") or "").strip()
    if not user_id:
        return error("user_id wajib ada", 400)

    files = request.files.getlist("images")
    if not files:
        return error("Kirim minimal satu file di field 'images'", 400)

    fcm_token = (request.form.get("fcm_token") or "").strip()
    if not fcm_token:
        return error("fcm_token wajib ada untuk registrasi perangkat", 400)

    try:
        # 1) Proses enroll wajah
        data = enroll_user(user_id, files)

        # 2) Ambil data perangkat dari form
        device_label = request.form.get("device_label") or None
        platform = request.form.get("platform") or None
        os_version = request.form.get("os_version") or None
        app_version = request.form.get("app_version") or None
        device_identifier = request.form.get("device_identifier") or None
        user_name = "Karyawan" # Default name

        # 3) Simpan/Update Device
        with get_session() as s:
            user = s.execute(
                select(User).where(User.id_user == user_id)
            ).scalar_one_or_none()
            if user is None:
                return error(
                    f"User dengan id_user '{user_id}' tidak ditemukan.",
                    404
                )
            user_name = user.nama_pengguna  # Ambil nama pengguna untuk notifikasi

            device = None
            if device_identifier:
                device = s.execute(
                    select(Device).where(
                        Device.id_user == user_id,
                        Device.device_identifier == device_identifier
                    )
                ).scalar_one_or_none()

            now_naive_utc = now_local().replace(tzinfo=None)

            if device is None:
                device = Device(
                    id_user=user_id,
                    device_label=device_label,
                    platform=platform,
                    os_version=os_version,
                    app_version=app_version,
                    device_identifier=device_identifier,
                    last_seen=now_naive_utc,
                    fcm_token=fcm_token,
                    fcm_token_updated_at=now_naive_utc
                )
                s.add(device)
            else:
                if device_label:
                    device.device_label = device_label
                if platform:
                    device.platform = platform
                if os_version:
                    device.os_version = os_version
                if app_version:
                    device.app_version = app_version
                device.last_seen = now_naive_utc
                if fcm_token:
                    device.fcm_token = fcm_token
                    device.fcm_token_updated_at = now_naive_utc

            try:
                s.commit()
            except IntegrityError as ie:
                s.rollback()
                return error(f"Gagal menyimpan device (integrity error): {str(ie.orig)}", 400)

            s.refresh(device)
            data["device_id"] = device.id_device

        # --- 4. Kirim Notifikasi ---
        try:
            send_notification(
                event_trigger='FACE_REGISTRATION_SUCCESS',
                user_id=user_id,
                dynamic_data={'nama_karyawan': user_name}
            )
        except Exception as e:
            # Jika notifikasi gagal, cukup catat log error tanpa menggagalkan respons utama
            current_app.logger.error(f"Gagal mengirim notifikasi registrasi wajah untuk user {user_id}: {e}")
        # --- Akhir ---

        return ok(**data)

    except Exception as e:
        current_app.logger.error(f"Kesalahan pada endpoint enroll: {e}", exc_info=True)
        return error(str(e), 400)


@face_bp.post("/verify")
def verify():
    user_id = (request.form.get("user_id") or "").strip()
    metric = (request.form.get("metric") or "cosine").lower()
    threshold = request.form.get("threshold", type=float, default=(0.45 if metric == "cosine" else 1.4))
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
        current_app.logger.error(f"Kesalahan pada endpoint verify: {e}", exc_info=True)
        return error(str(e), 400)


@face_bp.get("/<user_id>")
def get_face_data(user_id: str):
    user_id = (user_id or "").strip()
    if not user_id:
        return error("user_id wajib ada", 400)

    try:
        prefix = f"face_detection/{user_id}"

        items = list_objects(prefix)
        files = []
        for item in items:
            name = item.get("name") or item.get("Name")
            if not name:
                continue

            path = f"{prefix}/{name}"
            url = signed_url(path)
            files.append({
                "name": name,
                "path": path,
                "signed_url": url
            })

        return ok(user_id=user_id, prefix=prefix, count=len(files), items=files)
    except Exception as e:
        current_app.logger.error(f"Kesalahan pada endpoint get_face_data: {e}", exc_info=True)
        return error(str(e), 400)

