# flask_api_face/app/services/notification_service.py

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from firebase_admin import messaging
from sqlalchemy.orm import Session

from ..db.models import NotificationTemplate, Device, Notification


def _format_message(template: str, data: Dict[str, Any]) -> str:
    """Ganti placeholder di dalam template dengan data."""
    if not template:
        return ""
    result = template
    for key, value in data.items():
        token = f"{{{key}}}"
        result = result.replace(token, str(value) if value is not None else "")
    return result


def send_notification(event_trigger: str, user_id: str, dynamic_data: Dict[str, Any], session: Session) -> None:
    """Kirim notifikasi push untuk pengguna tertentu."""
    template: NotificationTemplate | None = (
        session.query(NotificationTemplate)
        .filter(
            NotificationTemplate.event_trigger == event_trigger,
            NotificationTemplate.is_active.is_(True),
        )
        .one_or_none()
    )
    if not template:
        return

    devices = (
        session.query(Device)
        .filter(
            Device.id_user == user_id,
            Device.fcm_token.isnot(None),
            Device.push_enabled.is_(True),
        )
        .all()
    )
    tokens = [d.fcm_token for d in devices if d.fcm_token]
    if not tokens:
        return

    title = _format_message(template.title_template, dynamic_data)
    body = _format_message(template.body_template, dynamic_data)

    notif = Notification(
        id_user=user_id,
        title=title,
        body=body,
        data_json=json.dumps(dynamic_data) if dynamic_data else None,
        created_at=datetime.utcnow(),
    )
    session.add(notif)
    session.commit()

    try:
        # --- PERUBAHAN UTAMA DI SINI ---
        # Siapkan payload 'data' untuk service worker.
        # Kuncinya harus string, dan nilainya juga harus string.
        data_payload = {
            "title": title,
            "body": body,
            # Anda bisa menambahkan data lain di sini jika diperlukan oleh aplikasi klien
            # Misalnya, URL untuk dibuka saat notifikasi di-klik
            "url": "/", 
        }

        message = messaging.MulticastMessage(
            tokens=tokens,
            # Payload 'notification' untuk saat aplikasi di foreground
            notification=messaging.Notification(title=title, body=body),
            # Payload 'data' untuk saat aplikasi di background/terminated
            data=data_payload,
            android=messaging.AndroidConfig(
                notification=messaging.AndroidNotification(sound="default")
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(aps=messaging.Aps(sound="default", content_available=True)),
            ),
        )
        messaging.send_multicast(message)
        # --- AKHIR PERUBAHAN ---
    except Exception as e:
        # Sebaiknya log error ini untuk debugging di masa depan
        print(f"Gagal mengirim notifikasi FCM: {e}")
        pass