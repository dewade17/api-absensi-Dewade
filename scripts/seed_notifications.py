# flask_api_face/scripts/seed_notifications.py

from sqlalchemy import select
from app import create_app
from app.db import get_session
from app.db.models import NotificationTemplate


# Daftar template notifikasi default
notification_templates = [
    # --- Notifikasi Wajah (BARU) ---
    {
        'eventTrigger': 'FACE_REGISTRATION_SUCCESS',
        'description': 'Konfirmasi saat karyawan berhasil mendaftarkan wajah',
        'titleTemplate': '✅ Wajah Berhasil Terdaftar',
        'bodyTemplate': 'Halo {nama_karyawan}, wajah Anda telah berhasil terdaftar pada sistem E-HRM. Anda kini dapat menggunakan fitur absensi wajah.',
        'placeholders': '{nama_karyawan}',
    },
    # --- Shift Kerja ---
    {
        'eventTrigger': 'NEW_SHIFT_PUBLISHED',
        'description': 'Info saat jadwal shift baru diterbitkan untuk karyawan',
        'titleTemplate': '📄 Jadwal Shift Baru Telah Terbit',
        'bodyTemplate': 'Jadwal shift kerja Anda untuk periode {periode_mulai} - {periode_selesai} telah tersedia. Silakan periksa.',
        'placeholders': '{nama_karyawan}, {periode_mulai}, {periode_selesai}',
    },
    {
    'eventTrigger': 'SHIFT_UPDATED',
    'description': 'Info saat ada perubahan pada jadwal shift karyawan',
    'titleTemplate': '🔄 Perubahan Jadwal Shift',
    'bodyTemplate': 'Perhatian, shift Anda pada tanggal {tanggal_shift} diubah menjadi {nama_shift} ({jam_masuk} - {jam_pulang}).',
    'placeholders': '{nama_karyawan}, {tanggal_shift}, {nama_shift}, {jam_masuk}, {jam_pulang}',
    },
    {
        'eventTrigger': 'SHIFT_REMINDER_H1',
        'description': 'Pengingat H-1 sebelum jadwal shift karyawan',
        'titleTemplate': '📢 Pengingat Shift Besok',
        'bodyTemplate': 'Jangan lupa, besok Anda masuk kerja pada shift {nama_shift} pukul {jam_masuk}.',
        'placeholders': '{nama_karyawan}, {nama_shift}, {jam_masuk}',
    },
    # --- Agenda Kerja ---
    {
        'eventTrigger': 'NEW_AGENDA_ASSIGNED',
        'description': 'Notifikasi saat karyawan diberikan agenda kerja baru',
        'titleTemplate': '✍️ Agenda Kerja Baru',
        'bodyTemplate': 'Anda mendapatkan tugas baru: "{judul_agenda}". Batas waktu pengerjaan hingga {tanggal_deadline}.',
        'placeholders': '{nama_karyawan}, {judul_agenda}, {tanggal_deadline}, {pemberi_tugas}',
    },
    {
        'eventTrigger': 'AGENDA_REMINDER_H1',
        'description': 'Pengingat H-1 sebelum deadline agenda kerja',
        'titleTemplate': '🔔 Pengingat Agenda Kerja',
        'bodyTemplate': 'Jangan lupa, agenda "{judul_agenda}" akan jatuh tempo besok. Segera perbarui statusnya.',
        'placeholders': '{nama_karyawan}, {judul_agenda}',
    },
    {
        'eventTrigger': 'AGENDA_OVERDUE',
        'description': 'Notifikasi saat agenda kerja melewati batas waktu',
        'titleTemplate': '⏰ Agenda Melewati Batas Waktu',
        'bodyTemplate': 'Perhatian, agenda kerja "{judul_agenda}" telah melewati batas waktu pengerjaan.',
        'placeholders': '{nama_karyawan}, {judul_agenda}',
    },
    {
        'eventTrigger': 'AGENDA_COMMENTED',
        'description': 'Notifikasi saat atasan/rekan memberi komentar pada agenda',
        'titleTemplate': '💬 Komentar Baru pada Agenda',
        'bodyTemplate': '{nama_komentator} memberikan komentar pada agenda "{judul_agenda}". Silakan periksa detailnya.',
        'placeholders': '{nama_karyawan}, {judul_agenda}, {nama_komentator}',
    },
    # --- Istirahat ---
    {
        'eventTrigger': 'SUCCESS_START_BREAK',
        'description': 'Konfirmasi saat karyawan memulai istirahat',
        'titleTemplate': '☕ Istirahat Dimulai',
        'bodyTemplate': 'Anda memulai istirahat pada pukul {waktu_mulai_istirahat}. Selamat menikmati waktu istirahat Anda!',
        'placeholders': '{nama_karyawan}, {waktu_mulai_istirahat}',
    },
    {
        'eventTrigger': 'SUCCESS_END_BREAK',
        'description': 'Konfirmasi saat karyawan mengakhiri istirahat',
        'titleTemplate': '✅ Istirahat Selesai',
        'bodyTemplate': 'Anda telah mengakhiri istirahat pada pukul {waktu_selesai_istirahat}. Selamat melanjutkan pekerjaan!',
        'placeholders': '{nama_karyawan}, {waktu_selesai_istirahat}',
    },
    {
        'eventTrigger': 'BREAK_TIME_EXCEEDED',
        'description': 'Notifikasi jika durasi istirahat melebihi batas',
        'titleTemplate': '❗ Waktu Istirahat Berlebih',
        'bodyTemplate': 'Perhatian, durasi istirahat Anda telah melebihi batas maksimal {maks_jam_istirahat} menit yang ditentukan.',
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