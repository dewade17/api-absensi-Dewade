"""Seeding default notification templates."""

from typing import Dict

from sqlalchemy import inspect, select, text
from sqlalchemy.exc import NoSuchTableError

from app import create_app
from app.db import get_session
from app.db.models import NotificationTemplate


# Daftar template notifikasi default
notification_templates = [
    # --- Notifikasi Wajah (BARU) ---
    {
        "event_trigger": "FACE_REGISTRATION_SUCCESS",
        "description": "Konfirmasi saat karyawan berhasil mendaftarkan wajah",
        "title_template": "✅ Wajah Berhasil Terdaftar",
        "body_template": "Halo {nama_karyawan}, wajah Anda telah berhasil terdaftar pada sistem E-HRM. Anda kini dapat menggunakan fitur absensi wajah.",
        "placeholders": "{nama_karyawan}",
    },
    # --- Shift Kerja ---
    {
        "event_trigger": "NEW_SHIFT_PUBLISHED",
        "description": "Info saat jadwal shift baru diterbitkan untuk karyawan",
        "title_template": "📄 Jadwal Shift Baru Telah Terbit",
        "body_template": "Jadwal shift kerja Anda untuk periode {periode_mulai} - {periode_selesai} telah tersedia. Silakan periksa.",
        "placeholders": "{nama_karyawan}, {periode_mulai}, {periode_selesai}",
    },
    {
        "event_trigger": "SHIFT_UPDATED",
        "description": "Info saat ada perubahan pada jadwal shift karyawan",
        "title_template": "🔄 Perubahan Jadwal Shift",
        "body_template": "Perhatian, shift Anda pada tanggal {tanggal_shift} diubah menjadi {nama_shift} ({jam_masuk} - {jam_pulang}).",
        "placeholders": "{nama_karyawan}, {tanggal_shift}, {nama_shift}, {jam_masuk}, {jam_pulang}",
    },
    {
        "event_trigger": "SHIFT_REMINDER_H1",
        "description": "Pengingat H-1 sebelum jadwal shift karyawan",
        "title_template": "📢 Pengingat Shift Besok",
        "body_template": "Jangan lupa, besok Anda masuk kerja pada shift {nama_shift} pukul {jam_masuk}.",
        "placeholders": "{nama_karyawan}, {nama_shift}, {jam_masuk}",
    },
    # --- Agenda Kerja ---
    {
        "event_trigger": "NEW_AGENDA_ASSIGNED",
        "description": "Notifikasi saat karyawan diberikan agenda kerja baru",
        "title_template": "✍️ Agenda Kerja Baru",
        "body_template": "Anda mendapatkan tugas baru: \"{judul_agenda}\". Batas waktu pengerjaan hingga {tanggal_deadline}.",
        "placeholders": "{nama_karyawan}, {judul_agenda}, {tanggal_deadline}, {pemberi_tugas}",
    },
    {
        "event_trigger": "AGENDA_REMINDER_H1",
        "description": "Pengingat H-1 sebelum deadline agenda kerja",
        "title_template": "🔔 Pengingat Agenda Kerja",
        "body_template": "Jangan lupa, agenda \"{judul_agenda}\" akan jatuh tempo besok. Segera perbarui statusnya.",
        "placeholders": "{nama_karyawan}, {judul_agenda}",
    },
    {
        "event_trigger": "AGENDA_OVERDUE",
        "description": "Notifikasi saat agenda kerja melewati batas waktu",
        "title_template": "⏰ Agenda Melewati Batas Waktu",
        "body_template": "Perhatian, agenda kerja \"{judul_agenda}\" telah melewati batas waktu pengerjaan.",
        "placeholders": "{nama_karyawan}, {judul_agenda}",
    },
    {
        "event_trigger": "AGENDA_COMMENTED",
        "description": "Notifikasi saat atasan/rekan memberi komentar pada agenda",
        "title_template": "💬 Komentar Baru pada Agenda",
        "body_template": "{nama_komentator} memberikan komentar pada agenda \"{judul_agenda}\". Silakan periksa detailnya.",
        "placeholders": "{nama_karyawan}, {judul_agenda}, {nama_komentator}",
    },
    # --- Istirahat ---
    {
        "event_trigger": "SUCCESS_START_BREAK",
        "description": "Konfirmasi saat karyawan memulai istirahat",
        "title_template": "☕ Istirahat Dimulai",
        "body_template": "Anda memulai istirahat pada pukul {waktu_mulai_istirahat}. Selamat menikmati waktu istirahat Anda!",
        "placeholders": "{nama_karyawan}, {waktu_mulai_istirahat}",
    },
    {
        "event_trigger": "SUCCESS_END_BREAK",
        "description": "Konfirmasi saat karyawan mengakhiri istirahat",
        "title_template": "✅ Istirahat Selesai",
        "body_template": "Anda telah mengakhiri istirahat pada pukul {waktu_selesai_istirahat}. Selamat melanjutkan pekerjaan!",
        "placeholders": "{nama_karyawan}, {waktu_selesai_istirahat}",
    },
    {
        "event_trigger": "BREAK_TIME_EXCEEDED",
        "description": "Notifikasi jika durasi istirahat melebihi batas",
        "title_template": "❗ Waktu Istirahat Berlebih",
        "body_template": "Perhatian, durasi istirahat Anda telah melebihi batas maksimal {maks_jam_istirahat} menit yang ditentukan.",
        "placeholders": "{nama_karyawan}, {maks_jam_istirahat}",
    },
]


def ensure_notification_template_schema(session) -> None:
    """Pastikan tabel notification_templates memiliki skema terbaru."""

    inspector = inspect(session.bind)

    try:
        existing_columns = {
            column["name"] for column in inspector.get_columns("notification_templates")
        }
    except NoSuchTableError:
        print("Tabel notification_templates belum ada. Membuat tabel...")
        NotificationTemplate.__table__.create(session.bind, checkfirst=True)
        session.commit()
        existing_columns = {
            column.name for column in NotificationTemplate.__table__.columns
        }

    column_ddl: Dict[str, str] = {
        "event_trigger": "ALTER TABLE notification_templates ADD COLUMN event_trigger VARCHAR(64) NULL",
        "description": "ALTER TABLE notification_templates ADD COLUMN description VARCHAR(255) NULL",
        "title_template": "ALTER TABLE notification_templates ADD COLUMN title_template VARCHAR(255) NULL",
        "body_template": "ALTER TABLE notification_templates ADD COLUMN body_template TEXT NULL",
        "placeholders": "ALTER TABLE notification_templates ADD COLUMN placeholders VARCHAR(255) NULL",
        "is_active": "ALTER TABLE notification_templates ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1",
        "created_at": "ALTER TABLE notification_templates ADD COLUMN created_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "ALTER TABLE notification_templates ADD COLUMN updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
    }

    for column_name, ddl in column_ddl.items():
        if column_name not in existing_columns:
            print(f"Kolom '{column_name}' belum ada. Menambahkan ke tabel notification_templates...")
            session.execute(text(ddl))
            session.commit()
            existing_columns.add(column_name)

    indexes = {index["name"] for index in inspector.get_indexes("notification_templates")}
    unique_index_name = "uq_notification_templates_event_trigger"
    if "event_trigger" in existing_columns and unique_index_name not in indexes:
        print("Menambahkan indeks unik untuk kolom event_trigger...")
        session.execute(
            text(
                "ALTER TABLE notification_templates "
                "ADD UNIQUE INDEX uq_notification_templates_event_trigger (event_trigger)"
            )
        )
        session.commit()


def seed_notifications() -> None:
    """Seed the notification_templates table with default templates."""

    print("Memulai seeding template notifikasi...")
    with get_session() as session:
        ensure_notification_template_schema(session)

        for template_data in notification_templates:
            stmt = select(NotificationTemplate).where(
                NotificationTemplate.event_trigger == template_data["event_trigger"]
            )
            exists = session.execute(stmt).scalar_one_or_none()

            if not exists:
                template = NotificationTemplate(**template_data)
                session.add(template)
                print(f"Template dibuat: {template_data['event_trigger']}")
            else:
                exists.description = template_data["description"]
                exists.title_template = template_data["title_template"]
                exists.body_template = template_data["body_template"]
                exists.placeholders = template_data.get("placeholders")
                exists.is_active = template_data.get("is_active", exists.is_active)
                print(f"Template sudah ada, diperbarui: {template_data['event_trigger']}")

        session.commit()
    print("Seeding template notifikasi selesai.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed_notifications()