import os
import firebase_admin
from firebase_admin import messaging
from app.db.models import Notification, Device, NotificationTemplate
from app.extensions import db

def format_message(template, data):
    """
    Mengganti placeholder di dalam string template dengan data dinamis.
    Contoh: template="Halo, {nama}!", data={"nama": "Budi"} -> "Halo, Budi!"
    """
    if not template:
        return ''
    message = template
    for key, value in data.items():
        message = message.replace(f'{{{key}}}', str(value))
    return message

def send_notification(event_trigger, user_id, dynamic_data):
    """
    Service utama untuk mengirim notifikasi ke pengguna.

    Args:
        event_trigger (str): Kode unik pemicu (cth: 'NEW_AGENDA_ASSIGNED').
        user_id (str): ID pengguna penerima.
        dynamic_data (dict): Data untuk mengisi placeholder di template.
    """
    # Pastikan Firebase sudah diinisialisasi sebelum mencoba mengirim
    if not firebase_admin._apps:
        print(f"Firebase tidak diinisialisasi. Melewatkan notifikasi untuk event: {event_trigger}")
        return

    try:
        # 1. Ambil template notifikasi dari database
        template = NotificationTemplate.query.filter_by(eventTrigger=event_trigger, isActive=True).first()

        title = f"Pemberitahuan Baru: {event_trigger}" # Default title
        body = "Anda memiliki pembaruan baru di aplikasi E-HRM." # Default body

        if template:
            print(f"Menggunakan template dari DB untuk [{event_trigger}].")
            title = format_message(template.titleTemplate, dynamic_data)
            body = format_message(template.bodyTemplate, dynamic_data)
        else:
            print(f"Peringatan: Template untuk [{event_trigger}] tidak ditemukan atau tidak aktif. Menggunakan pesan default.")

        # 2. Simpan riwayat notifikasi ke database
        new_notif = Notification(id_user=user_id, title=title, body=body)
        db.session.add(new_notif)
        db.session.commit()
        print(f"Notifikasi untuk [{event_trigger}] berhasil disimpan ke DB untuk user {user_id}.")

        # 3. Ambil semua token FCM milik pengguna yang aktif
        devices = Device.query.filter_by(id_user=user_id, push_enabled=True).filter(Device.fcm_token.isnot(None)).all()
        tokens = [device.fcm_token for device in devices]

        if not tokens:
            print(f"Tidak ada token FCM yang ditemukan untuk user {user_id}. Notifikasi push tidak dikirim.")
            return

        # 4. Buat pesan push notification
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            tokens=tokens,
            android=messaging.AndroidConfig(
                notification=messaging.AndroidNotification(sound='default')
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound='default')
                )
            )
        )

        # 5. Kirim notifikasi menggunakan Firebase Admin SDK
        response = messaging.send_multicast(message)
        print(f"Notifikasi push [{event_trigger}] berhasil dikirim ke {response.success_count} perangkat untuk user {user_id}.")
        
        if response.failure_count > 0:
            responses = response.responses
            failed_tokens = []
            for idx, resp in enumerate(responses):
                if not resp.success:
                    failed_tokens.append(tokens[idx])
            print('Daftar token yang gagal:', failed_tokens)

    except Exception as e:
        db.session.rollback()
        print(f"Gagal mengirim notifikasi {event_trigger} untuk user {user_id}: {e}")
