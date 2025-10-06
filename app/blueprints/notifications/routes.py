"""
Blueprint untuk registrasi token Firebase Cloud Messaging (FCM).

Endpoint ``POST /api/notifications`` menerima JSON berisi ``user_id`` dan
``token`` serta metadata perangkat. Endpoint ini akan menyimpan atau
memperbarui baris pada tabel ``Device``. Jika token sudah ada untuk user
yang sama, record diperbarui dengan timestamp terkini dan flag ``push_enabled``
dinyalakan kembali.

Contoh request body:

```
{
  "user_id": "uuid-user",
  "token": "fcm_token_here",
  "deviceIdentifier": "unique-device-id",
  "deviceLabel": "iPhone 13",
  "platform": "iOS",
  "osVersion": "16.0",
  "appVersion": "1.0.0"
}
```

Response akan mengembalikan ``{ ok: True, message: "Device token registered" }``.
"""

from flask import Blueprint, request
from ..utils.responses import ok, error
from ..db import get_session
from ..db.models import Device
from ..utils.timez import now_local

notif_bp = Blueprint("notifications", __name__)


@notif_bp.post("/api/notifications")
def register_token():
    """Registrasi atau update token FCM untuk user tertentu."""
    try:
        data = request.get_json(force=True)
    except Exception:
        return error("Invalid JSON body", 400)

    user_id = (data.get("user_id") or "").strip()
    token = (data.get("token") or "").strip()

    if not user_id or not token:
        return error("user_id dan token wajib ada", 400)

    device_identifier = (data.get("deviceIdentifier") or "").strip() or None
    device_label = (data.get("deviceLabel") or "").strip() or None
    platform = (data.get("platform") or "").strip() or None
    os_version = (data.get("osVersion") or "").strip() or None
    app_version = (data.get("appVersion") or "").strip() or None

    with get_session() as session:
        existing = (
            session.query(Device)
            .filter(Device.id_user == user_id, Device.fcm_token == token)
            .one_or_none()
        )
        now_dt = now_local().replace(tzinfo=None)

        if existing:
            # update token data
            if device_label:
                existing.device_label = device_label
            if platform:
                existing.platform = platform
            if os_version:
                existing.os_version = os_version
            if app_version:
                existing.app_version = app_version
            if device_identifier:
                existing.device_identifier = device_identifier
            existing.fcm_token_updated_at = now_dt
            existing.last_seen = now_dt
            existing.push_enabled = True
            existing.failed_push_count = 0
        else:
            rec = Device(
                id_user=user_id,
                device_label=device_label,
                platform=platform,
                os_version=os_version,
                app_version=app_version,
                device_identifier=device_identifier,
                fcm_token=token,
                fcm_token_updated_at=now_dt,
                last_seen=now_dt,
                push_enabled=True,
            )
            session.add(rec)

        session.commit()

    return ok(message="Device token registered")