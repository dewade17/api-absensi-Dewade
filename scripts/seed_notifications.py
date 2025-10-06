# flask_api_face/scripts/seed_notifications.py

from sqlalchemy import select
from app import create_app
from app.db import get_session
from app.db.models import NotificationTemplate


# Daftar template notifikasi default
notification_templates = [
    # --- Notifikasi Wajah (BARU) ---
    {
        'event_trigger': 'FACE_REGISTRATION_SUCCESS',
        'description': 'Konfirmasi saat karyawan berhasil mendaftarkan wajah',
        'title_template': '✅ Wajah Berhasil Terdaftar',
        'body_template': 'Halo {nama_karyawan}, wajah Anda telah berhasil terdaftar pada sistem E-HRM. Anda kini dapat menggunakan fitur absensi wajah.',
        'placeholders': '{nama_karyawan}',
    },
    # --- Shift Kerja ---
    {
        'event_trigger': 'NEW_SHIFT_PUBLISHED',
        'description': 'Info saat jadwal shift baru diterbitkan untuk karyawan',
        'title_template': '📄 Jadwal Shift Baru Telah Terbit',
        'body_template': 'Jadwal shift kerja Anda untuk periode {periode_mulai} - {periode_selesai} telah tersedia. Silakan periksa.',
        'placeholders': '{nama_karyawan}, {periode_mulai}, {periode_selesai}',
    },
    {
    'event_trigger': 'SHIFT_UPDATED',
    'description': 'Info saat ada perubahan pada jadwal shift karyawan',
    'title_template': '🔄 Perubahan Jadwal Shift',
    'body_template': 'Perhatian, shift Anda pada tanggal {tanggal_shift} diubah menjadi {nama_shift} ({jam_masuk} - {jam_pulang}).',
    'placeholders': '{nama_karyawan}, {tanggal_shift}, {nama_shift}, {jam_masuk}, {jam_pulang}',
    },
    {
        'event_trigger': 'SHIFT_REMINDER_H1',
        'description': 'Pengingat H-1 sebelum jadwal shift karyawan',
        'title_template': '📢 Pengingat Shift Besok',
        'body_template': 'Jangan lupa, besok Anda masuk kerja pada shift {nama_shift} pukul {jam_masuk}.',
        'placeholders': '{nama_karyawan}, {nama_shift}, {jam_masuk}',
    },
    # --- Agenda Kerja ---
    {
        'event_trigger': 'NEW_AGENDA_ASSIGNED',
        'description': 'Notifikasi saat karyawan diberikan agenda kerja baru',
        'title_template': '✍️ Agenda Kerja Baru',
        'body_template': 'Anda mendapatkan tugas baru: "{judul_agenda}". Batas waktu pengerjaan hingga {tanggal_deadline}.',
        'placeholders': '{nama_karyawan}, {judul_agenda}, {tanggal_deadline}, {pemberi_tugas}',
    },
    {
        'event_trigger': 'AGENDA_REMINDER_H1',
        'description': 'Pengingat H-1 sebelum deadline agenda kerja',
        'title_template': '🔔 Pengingat Agenda Kerja',
        'body_template': 'Jangan lupa, agenda "{judul_agenda}" akan jatuh tempo besok. Segera perbarui statusnya.',
        'placeholders': '{nama_karyawan}, {judul_agenda}',
    },
    {
        'event_trigger': 'AGENDA_OVERDUE',
        'description': 'Notifikasi saat agenda kerja melewati batas waktu',
        'title_template': '⏰ Agenda Melewati Batas Waktu',
        'body_template': 'Perhatian, agenda kerja "{judul_agenda}" telah melewati batas waktu pengerjaan.',
        'placeholders': '{nama_karyawan}, {judul_agenda}',
    },
    {
        'event_trigger': 'AGENDA_COMMENTED',
        'description': 'Notifikasi saat atasan/rekan memberi komentar pada agenda',
        'title_template': '💬 Komentar Baru pada Agenda',
        'body_template': '{nama_komentator} memberikan komentar pada agenda "{judul_agenda}". Silakan periksa detailnya.',
        'placeholders': '{nama_karyawan}, {judul_agenda}, {nama_komentator}',
    },
    # --- Istirahat ---
    {
        'event_trigger': 'SUCCESS_START_BREAK',
        'description': 'Konfirmasi saat karyawan memulai istirahat',
        'title_template': '☕ Istirahat Dimulai',
        'body_template': 'Anda memulai istirahat pada pukul {waktu_mulai_istirahat}. Selamat menikmati waktu istirahat Anda!',
        'placeholders': '{nama_karyawan}, {waktu_mulai_istirahat}',
    },
    {
        'event_trigger': 'SUCCESS_END_BREAK',
        'description': 'Konfirmasi saat karyawan mengakhiri istirahat',
        'title_template': '✅ Istirahat Selesai',
        'body_template': 'Anda telah mengakhiri istirahat pada pukul {waktu_selesai_istirahat}. Selamat melanjutkan pekerjaan!',
        'placeholders': '{nama_karyawan}, {waktu_selesai_istirahat}',
    },
    {
        'event_trigger': 'BREAK_TIME_EXCEEDED',
        'description': 'Notifikasi jika durasi istirahat melebihi batas',
        'title_template': '❗ Waktu Istirahat Berlebih',
        'body_template': 'Perhatian, durasi istirahat Anda telah melebihi batas maksimal {maks_jam_istirahat} menit yang ditentukan.',
        'placeholders': '{nama_karyawan}, {maks_jam_istirahat}',
    },
]

def seed_notifications():
    """Seed the notification_templates table with default templates."""
    print("Memulai seeding template notifikasi...")
    with get_session() as session:
        for template_data in notification_templates:
            # Cek apakah template sudah ada menggunakan session SQLAlchemy
            stmt = select(NotificationTemplate).where(NotificationTemplate.event_trigger == template_data['event_trigger'])
            exists = session.execute(stmt).scalar_one_or_none()

            if not exists:
                # Jika belum ada, buat baru
                template = NotificationTemplate(**template_data)
                session.add(template)
                print(f"Template dibuat: {template_data['event_trigger']}")
            else:
                # Jika sudah ada, perbarui deskripsi, judul, dan isi
                exists.description = template_data['description']
                exists.title_template = template_data['title_template']
                exists.body_template = template_data['body_template']
                exists.placeholders = template_data.get('placeholders')
                exists.is_active = template_data.get('is_active', exists.is_active)
                print(f"Template sudah ada, diperbarui: {template_data['event_trigger']}")

        session.commit()
    print("Seeding template notifikasi selesai.")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        seed_notifications()