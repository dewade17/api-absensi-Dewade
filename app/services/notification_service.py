# flask_api_face/app/services/notification_service.py

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from firebase_admin import messaging
# Pastikan Firebase Admin SDK telah diinisialisasi sebelum mengirim notifikasi.
from ..firebase import initialize_firebase
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
    """
    Kirim notifikasi push untuk pengguna tertentu.

    Fungsi ini mencari template berdasarkan `event_trigger`, mengambil daftar token
    FCM aktif untuk pengguna, kemudian menyusun pesan dan mengirimkannya
    menggunakan API terbaru `send_each_for_multicast()` dari Firebase Admin SDK.
    """

    # Inisialisasi Firebase Admin SDK jika belum diinisialisasi.
    try:
        initialize_firebase()
    except Exception:
        pass

    # Ambil template notifikasi yang aktif sesuai event trigger.
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

    # Ambil device FCM tokens untuk user yang bersangkutan yang masih aktif.
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

    # Format judul dan isi pesan dengan mengganti placeholder pada template.
    title = _format_message(template.title_template, dynamic_data)
    body = _format_message(template.body_template, dynamic_data)

    # Simpan notifikasi ke database untuk keperluan log/riwayat.
    notif = Notification(
        id_user=user_id,
        title=title,
        body=body,
        data_json=json.dumps(dynamic_data) if dynamic_data else None,
        created_at=datetime.utcnow(),
    )
    session.add(notif)
    session.commit()

    # Bangun payload data tambahan yang akan diterima oleh service worker.
    data_payload = {
        "title": title,
        "body": body,
        # Tambahkan data lain (mis. URL) sesuai kebutuhan aplikasi klien.
        "url": "/",
    }

    # Susun objek MulticastMessage. Properti `notification` dipakai saat
    # aplikasi di foreground, sedangkan properti `data` dipakai oleh service
    # worker ketika aplikasi di background/terminated.
    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(title=title, body=body),
        data=data_payload,
        android=messaging.AndroidConfig(
            notification=messaging.AndroidNotification(sound="default")
        ),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound="default", content_available=True)
            ),
        ),
    )

    try:
        # Gunakan API baru send_each_for_multicast() untuk mengirim pesan ke setiap
        # token. Ini menggantikan send_multicast() yang telah dihapus pada
        # Firebase Admin SDK v7.0.0.
        responses = messaging.send_each_for_multicast(message)
        # Hitung jumlah keberhasilan/gagal untuk keperluan logging (opsional).
        success_count = sum(1 for r in responses if r.success)
        failure_count = len(responses) - success_count
        # Cetak ringkasan kirim. Ini bisa diganti dengan logging.
        print(f"Notifikasi dikirim: {success_count} sukses, {failure_count} gagal")
    except Exception as e:
        # Tangkap dan log exception tanpa menghentikan alur aplikasi.
        print(f"Gagal mengirim notifikasi FCM: {e}")
