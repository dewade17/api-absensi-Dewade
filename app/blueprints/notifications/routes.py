# flask_api_face/app/blueprints/notifications/routes.py

from __future__ import annotations

from flask import Blueprint, request, current_app
from sqlalchemy import select

from ...db import get_session
from ...db.models import Device, Notification
from ...utils.responses import ok, error
from ...utils.auth_utils import token_required, get_user_id_from_auth
from ...utils.timez import now_local

# Penting: JANGAN menaruh prefix "/api/notifications" di sini.
# Prefix dipasang saat register_blueprint() di create_app():
# app.register_blueprint(notif_bp, url_prefix="/api/notifications")
notif_bp = Blueprint("notifications", __name__)


@notif_bp.post("/device/register")
@token_required
def register_device():
    """
    Mendaftarkan atau memperbarui token FCM untuk sebuah perangkat.
    Endpoint akhir: POST /api/notifications/device/register
    Body (JSON): { fcm_token, device_identifier, platform?, os_version?, app_version?, device_label? }
    """
    user_id = get_user_id_from_auth()
    payload = request.get_json(silent=True)
    if not payload:
        return error("JSON body tidak valid", 400)

    fcm_token = (payload.get("fcm_token") or "").strip()
    device_identifier = (payload.get("device_identifier") or "").strip()

    if not fcm_token:
        return error("Field 'fcm_token' wajib ada", 400)

    with get_session() as s:
        device = None
        if device_identifier:
            device = (
                s.execute(
                    select(Device).where(
                        Device.id_user == user_id,
                        Device.device_identifier == device_identifier,
                    )
                )
                .scalar_one_or_none()
            )

        now_naive_utc = now_local().replace(tzinfo=None)

        if device:
            # Update device
            device.fcm_token = fcm_token
            device.fcm_token_updated_at = now_naive_utc
            device.last_seen = now_naive_utc
            device.platform = payload.get("platform")
            device.os_version = payload.get("os_version")
            device.app_version = payload.get("app_version")
            device.device_label = payload.get("device_label")
            msg = "Token perangkat diperbarui"
        else:
            # Create new device
            device = Device(
                id_user=user_id,
                fcm_token=fcm_token,
                device_identifier=device_identifier,
                platform=payload.get("platform"),
                os_version=payload.get("os_version"),
                app_version=payload.get("app_version"),
                device_label=payload.get("device_label"),
                fcm_token_updated_at=now_naive_utc,
                last_seen=now_naive_utc,
            )
            s.add(device)
            msg = "Perangkat berhasil didaftarkan"

        s.commit()
        s.refresh(device)

        return ok(message=msg, device_id=device.id_device)


@notif_bp.get("/")
@token_required
def get_notifications():
    """
    Mengambil daftar notifikasi untuk pengguna yang terautentikasi.
    Endpoint akhir: GET /api/notifications
    """
    user_id = get_user_id_from_auth()
    with get_session() as s:
        notifications = (
            s.execute(
                select(Notification)
                .where(Notification.id_user == user_id)
                .order_by(Notification.created_at.desc())
            )
            .scalars()
            .all()
        )

        def to_dict(n: Notification):
            return {
                "id_notification": n.id_notification,
                "title": n.title,
                "body": n.body,
                "created_at": n.created_at.isoformat(),
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "status": n.status.value if n.status else None,
            }

        return ok(items=[to_dict(n) for n in notifications])


@notif_bp.put("/<string:notification_id>/read")
@token_required
def mark_as_read(notification_id: str):
    """
    Menandai notifikasi sebagai 'read'.
    Endpoint akhir: PUT /api/notifications/<notification_id>/read
    """
    user_id = get_user_id_from_auth()
    with get_session() as s:
        result = (
            s.query(Notification)
            .filter(
                Notification.id_notification == notification_id,
                Notification.id_user == user_id,
            )
            .one_or_none()
        )

        if not result:
            return error("Notifikasi tidak ditemukan atau Anda tidak punya akses", 404)

        if not result.read_at:
            result.read_at = now_local().replace(tzinfo=None)
            # Jika kolom status bertipe Enum, pastikan assignment sesuai tipe Enum
            try:
                result.status = getattr(result.__class__.status.type.enum_class, "read")  # type: ignore
            except Exception:
                # fallback bila status berupa string
                result.status = "read"  # type: ignore
            s.commit()

        return ok(message="Notifikasi ditandai sebagai sudah dibaca")
