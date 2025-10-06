"""
Script untuk memasukkan template notifikasi awal ke database.

Jalankan skrip ini dengan context Python di root aplikasi Flask. Skrip akan
melakukan upsert (insert jika tidak ada) terhadap setiap template yang
didefinisikan di ``notificationTemplates``. Jika sebuah template sudah
terdaftar (berdasarkan ``event_trigger``), skrip tidak akan mengubahnya.

Contoh penggunaan:

    python -m flask_api_face.scripts.seed_notifications
"""

from ..db import get_session
from ..db.models import NotificationTemplate


notificationTemplates = [
    {
        "event_trigger": "REMINDER_CHECK_IN",
        "description": "Pengingat 15 menit sebelum jam masuk",
        "title_template": "⏰ Jangan Lupa Absen Masuk!",
        "body_template": "Shift kerja Anda akan dimulai pukul {jam_masuk}. Segera lakukan absensi check-in.",
        "placeholders": "{nama_karyawan}, {jam_masuk}",
    },
    {
        "event_trigger": "SUCCESS_CHECK_IN",
        "description": "Konfirmasi saat berhasil check-in",
        "title_template": "✅ Absen Masuk Berhasil",
        "body_template": "Anda berhasil check-in pada pukul {waktu_checkin}. Selamat bekerja, {nama_karyawan}!",
        "placeholders": "{nama_karyawan}, {waktu_checkin}",
    },
    {
        "event_trigger": "LATE_CHECK_IN",
        "description": "Notifikasi saat karyawan check-in terlambat",
        "title_template": "⚠️ Anda Terlambat Masuk",
        "body_template": "Anda tercatat check-in pada pukul {waktu_checkin}, melewati jadwal masuk Anda pukul {jam_masuk}.",
        "placeholders": "{nama_karyawan}, {waktu_checkin}, {jam_masuk}",
    },
    {
        "event_trigger": "REMINDER_CHECK_OUT",
        "description": "Pengingat 15 menit sebelum jam pulang",
        "title_template": "⏰ Waktunya Absen Pulang",
        "body_template": "Shift kerja Anda akan berakhir pukul {jam_pulang}. Jangan lupa lakukan absensi check-out.",
        "placeholders": "{nama_karyawan}, {jam_pulang}",
    },
    {
        "event_trigger": "SUCCESS_CHECK_OUT",
        "description": "Konfirmasi saat berhasil check-out",
        "title_template": "✅ Absen Pulang Berhasil",
        "body_template": "Anda berhasil melakukan check-out pada pukul {waktu_checkout}. Terima kasih untuk hari ini.",
        "placeholders": "{nama_karyawan}, {waktu_checkout}",
    },
    {
        "event_trigger": "MISSED_CHECK_IN",
        "description": "Notifikasi jika karyawan tidak melakukan check-in",
        "title_template": "❗ Anda Belum Absen Masuk",
        "body_template": "Sistem mencatat Anda belum melakukan check-in untuk shift hari ini. Mohon konfirmasi ke atasan Anda.",
        "placeholders": "{nama_karyawan}",
    },
]


def seed_templates():
    """Masukkan template notifikasi ke database jika belum ada."""
    with get_session() as session:
        for tpl in notificationTemplates:
            existing = (
                session.query(NotificationTemplate)
                .filter(NotificationTemplate.event_trigger == tpl["event_trigger"])
                .one_or_none()
            )
            if existing:
                continue
            rec = NotificationTemplate(**tpl)
            session.add(rec)
        session.commit()


if __name__ == "__main__":
    seed_templates()