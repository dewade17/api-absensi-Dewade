"""
Layanan untuk mengirim notifikasi menggunakan Firebase Cloud Messaging.

Fungsi utama dalam modul ini adalah ``send_notification`` yang menerima kode
``event_trigger``, ID pengguna, data dinamis untuk mengganti placeholder,
serta session SQLAlchemy. Fungsi ini akan:

1. Mengambil template notifikasi dari tabel ``NotificationTemplate`` berdasarkan
   event trigger dan hanya jika template aktif.
2. Mengambil daftar token FCM dari tabel ``Device`` untuk pengguna bersangkutan
   yang masih memiliki ``push_enabled=True`` dan token tidak kosong.
3. Memformat judul dan isi pesan dengan mengganti placeholder di template
   menggunakan data dinamis.
4. Menyimpan rekam notifikasi ke tabel ``Notification`` untuk kebutuhan
   in‑app notification/history.
5. Mengirim push notification ke Firebase Cloud Messaging.

Template notifikasi memanfaatkan placeholder dalam bentuk ``{placeholder}``.
Data dinamis yang dikirim harus berupa dict dengan kunci yang sesuai.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from firebase_admin import messaging
from sqlalchemy.orm import Session

from ..db.models import NotificationTemplate, Device, Notification


def _format_message(template: str, data: Dict[str, Any]) -> str:
    """Ganti placeholder di dalam template dengan data.

    Parameter ``template`` adalah string yang mungkin berisi token seperti
    ``{nama_karyawan}`` yang harus digantikan dengan nilai dari ``data``.
    Jika placeholder tidak ditemukan dalam ``data``, token tidak akan diganti.

    Args:
        template: String template yang berisi token.
        data: Dict berisi nilai pengganti. Nilai akan di-cast menjadi string.

    Returns:
        String yang telah diformat.
    """
    if not template:
        return ""
    result = template
    for key, value in data.items():
        token = f"{{{key}}}"
        result = result.replace(token, str(value) if value is not None else "")
    return result


def send_notification(event_trigger: str, user_id: str, dynamic_data: Dict[str, Any], session: Session) -> None:
    """Kirim notifikasi push untuk pengguna tertentu.

    Args:
        event_trigger: Kode pemicu template notifikasi.
        user_id: ID pengguna penerima.
        dynamic_data: Data untuk mengganti placeholder dalam template.
        session: Session SQLAlchemy aktif.

    Returns:
        None. Jika tidak ada template atau token, fungsi mengembalikan tanpa
        mengirim notifikasi.
    """
    # 1. Ambil template notifikasi dari DB
    template: NotificationTemplate | None = (
        session.query(NotificationTemplate)
        .filter(
            NotificationTemplate.event_trigger == event_trigger,
            NotificationTemplate.is_active.is_(True),
        )
        .one_or_none()
    )
    if not template:
        # Template tidak tersedia atau tidak aktif
        return

    # 2. Ambil semua device user dengan token FCM
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
        # Tidak ada token yang dapat dikirim
        return

    # 3. Format judul dan isi pesan
    title = _format_message(template.title_template, dynamic_data)
    body = _format_message(template.body_template, dynamic_data)

    # 4. Simpan riwayat notifikasi ke tabel Notification
    notif = Notification(
        id_user=user_id,
        title=title,
        body=body,
        data_json=json.dumps(dynamic_data) if dynamic_data else None,
        created_at=datetime.utcnow(),
    )
    session.add(notif)
    session.commit()

    # 5. Kirim push ke FCM
    try:
        message = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(title=title, body=body),
            android=messaging.AndroidConfig(
                notification=messaging.AndroidNotification(sound="default")
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(aps=messaging.Aps(sound="default"))
            ),
        )
        messaging.send_multicast(message)
    except Exception:
        # Jangan melempar error ke API; log dapat ditambahkan di masa depan.
        pass
