# app/services/notification_service.py

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List
import logging # <-- Ditambahkan

from firebase_admin import messaging
from sqlalchemy.orm import Session

# Coba impor initialize_firebase dari extensions; jika tidak ada, pakai app/firebase.py
try:
    from ..extensions import initialize_firebase # beberapa branch menamai begini
except (ImportError, AttributeError):
    from ..firebase import initialize_firebase # fallback yang ada di repo kamu

from ..db.models import NotificationTemplate, Device, Notification

logger = logging.getLogger(__name__)
# ---------- Helpers ----------

def _format_message(template: str, data: Dict[str, Any]) -> str:
    """Ganti placeholder {key} di template dengan data[key] tanpa meledak bila tidak ada."""
    if not template:
        return ""
    try:
        return template.format(**data)
    except Exception:
        # Log jika terjadi error saat formatting (opsional, tapi berguna)
        logger.warning(f"Gagal memformat template: '{template[:50]}...' dengan data: {list(data.keys())}", exc_info=False)
        return template


def _send_multicast_compat(message: messaging.MulticastMessage, tokens: List[str]):
    """
    Kirim multicast dengan kompatibilitas lintas versi firebase_admin.

    Return object dengan atribut:
      - success_count: int
      - failure_count: int
      - responses: list objek yang punya .success: bool
    """
    # 1) Versi baru & paling umum
    if hasattr(messaging, "send_multicast"):
        return messaging.send_multicast(message) # type: ignore[attr-defined]

    # 2) Ada di beberapa versi: kirim tiap item (namun tetap satu call)
    if hasattr(messaging, "send_each_for_multicast"):
        resp = messaging.send_each_for_multicast(message) # type: ignore[attr-defined]
        success = sum(1 for r in resp.responses if getattr(r, "success", False))
        failure = len(resp.responses) - success

        class _Compat:
            def __init__(self, success_count, failure_count, responses):
                self.success_count = success_count
                self.failure_count = failure_count
                self.responses = responses

        return _Compat(success, failure, resp.responses)

    # 3) Versi lama: konstruksi messages dan gunakan send_all jika ada
    common_kwargs = dict(
        data=message.data,
        android=message.android,
        apns=message.apns,
        webpush=getattr(message, "webpush", None),
        fcm_options=getattr(message, "fcm_options", None),
        notification=getattr(message, "notification", None), # biasanya None krn kita pakai data-only
    )
    messages = [messaging.Message(token=t, **common_kwargs) for t in tokens]

    if hasattr(messaging, "send_all"):
        resp = messaging.send_all(messages) # type: ignore[attr-defined]

        class _Compat:
            def __init__(self, success_count, failure_count, responses):
                self.success_count = success_count
                self.failure_count = failure_count
                self.responses = responses

        return _Compat(resp.success_count, resp.failure_count, resp.responses)

    # 4) Fallback terakhir: kirim satu-per-satu
    responses = []
    success = 0
    for msg in messages:
        try:
            messaging.send(msg)
            class _R: success = True
            responses.append(_R())
            success += 1
        except Exception as e:
            # Log error saat mengirim individual message
            logger.warning(f"Gagal mengirim FCM ke token individual: {e}", exc_info=False)
            class _R: success = False
            responses.append(_R())

    class _Compat:
        def __init__(self, success_count, failure_count, responses):
            self.success_count = success_count
            self.failure_count = failure_count
            self.responses = responses

    return _Compat(success, len(messages) - success, responses)


# ---------- Public API ----------

def send_notification(event_trigger: str, user_id: str, dynamic_data: Dict[str, Any], session: Session) -> None:
    """
    Kirim notifikasi push untuk user tertentu berdasarkan NotificationTemplate.event_trigger.
    - Simpan record ke tabel notifications (tanpa kolom event_trigger, karena memang tidak ada).
    - Kirim FCM sebagai 'data message' agar andal di background.
    """
    # Pastikan Firebase Admin siap (tidak fatal kalau gagal)
    try:
        initialize_firebase()
    except Exception as e:
        # Ganti print dengan logger.warning
        logger.warning(f"Gagal menginisialisasi Firebase saat mengirim notifikasi: {e}", exc_info=True) # exc_info=True untuk traceback

    # Ambil template aktif
    template: NotificationTemplate | None = (
        session.query(NotificationTemplate)
        .filter(
            NotificationTemplate.event_trigger == event_trigger,
            NotificationTemplate.is_active.is_(True),
        )
        .one_or_none()
    )
    if not template:
        # Ganti print dengan logger.warning
        logger.warning(f"Template notifikasi untuk event '{event_trigger}' tidak ditemukan/ tidak aktif.")
        return

    # Ambil token device aktif
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
        # Ganti print dengan logger.warning
        logger.warning(f"Tidak ada device/token FCM aktif untuk user '{user_id}'.")
        return

    # Render judul & body dari template
    title = _format_message(template.title_template or "", dynamic_data)
    body = _format_message(template.body_template or "", dynamic_data)

    # Simpan record notifikasi ke DB (TANPA event_trigger, karena kolom itu tidak ada di model Notification)
    notif = Notification(
        id_user=user_id,
        title=title,
        body=body,
        # Masukkan event_trigger & dynamic_data ke data_json supaya tetap terlacak di sisi server
        data_json=json.dumps(
            {"event_trigger": event_trigger, "meta": dynamic_data},
            default=str
        ),
        # Optional: related_table/related_id bisa diisi oleh caller di masa depan
        created_at=datetime.utcnow(),
    )
    try:
        session.add(notif)
        session.flush() # dapatkan id_notification untuk dipakai di payload
        logger.info(f"Notification record created for user '{user_id}' with ID: {notif.id_notification}")
    except Exception as e:
        session.rollback()
        logger.error(f"Gagal menyimpan record notifikasi ke DB untuk user '{user_id}': {e}", exc_info=True)
        return # Hentikan proses jika gagal simpan ke DB

    # Susun payload FCM sebagai DATA MESSAGE agar bisa diterima di background (Android/iOS)
    data_payload: Dict[str, str] = {
        "title": title,
        "body": body,
        "notification_id": str(notif.id_notification),
        "event_trigger": event_trigger,
        # Klien bisa parse 'meta' untuk detail tambahan (status_absensi, jam, dll)
        "meta": json.dumps(dynamic_data, default=str),
    }

    multicast = messaging.MulticastMessage(
        tokens=tokens,
        data=data_payload,
        android=messaging.AndroidConfig(priority="high"),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(content_available=True)
            )
        ),
    )

    # Kirim notifikasi (kompatibel lintas versi Admin SDK)
    try:
        response = _send_multicast_compat(multicast, tokens)
        # Ganti print dengan logger.info
        logger.info(
            f"Notifikasi dikirim untuk user '{user_id}': "
            f"{response.success_count} sukses, {response.failure_count} gagal"
        )
        if getattr(response, "failure_count", 0):
            failed_tokens = []
            for idx, resp in enumerate(getattr(response, "responses", []) or []):
                if not getattr(resp, "success", False):
                    failed_tokens.append(tokens[idx])
            if failed_tokens:
                 # Ganti print dengan logger.warning
                logger.warning(f"Token FCM yang gagal untuk user '{user_id}': {failed_tokens}")
                # TODO: tandai token gagal (disable / hapus) di DB bila diperlukan
    except Exception as e:
        # --- Ganti print dengan logger.exception ---
        logger.exception(f"Gagal total mengirim notifikasi FCM untuk user '{user_id}': {e}")
        # Rollback DB commit jika FCM gagal? Tergantung kebutuhan.
        # Jika notifikasi di DB harus ada walau push gagal, jangan rollback.
        # Jika notifikasi DB hanya relevan jika push berhasil, uncomment rollback di bawah.
        # session.rollback()
        # return # Hentikan jika FCM gagal

    # Commit perubahan DB (jika tidak di-rollback di atas)
    try:
        session.commit()
    except Exception as e:
        session.rollback()
         # Ganti print dengan logger.error
        logger.error(f"Gagal commit notifikasi ke DB untuk user '{user_id}': {e}", exc_info=True)