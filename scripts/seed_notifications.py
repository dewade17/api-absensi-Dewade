# scripts/seed_notifications.py
"""Seeding default notification templates."""

from typing import Dict

from sqlalchemy import inspect, select, text
from sqlalchemy.exc import NoSuchTableError

from app import create_app
from app.db import get_session
from app.db.models import NotificationTemplate


# Daftar template notifikasi default
# templates.py
notification_templates = [
    # --- Notifikasi Wajah (BARU) ---
    {
        'event_trigger': 'FACE_REGISTRATION_SUCCESS', # <-- DIUBAH
        'description': 'Konfirmasi saat karyawan berhasil mendaftarkan wajah',
        'title_template': '✅ Wajah Berhasil Terdaftar', # <-- DIUBAH
        'body_template': 'Halo {nama_karyawan}, wajah Anda telah berhasil terdaftar pada sistem E-HRM. Anda kini dapat menggunakan fitur absensi wajah.', # <-- DIUBAH
        'placeholders': '{nama_karyawan}',
    },

    # --- Shift Kerja ---
    {
        'event_trigger': 'NEW_SHIFT_PUBLISHED', # <-- DIUBAH
        'description': 'Info saat jadwal shift baru diterbitkan untuk karyawan',
        'title_template': '📄 Jadwal Shift Baru Telah Terbit', # <-- DIUBAH
        'body_template': 'Jadwal shift kerja Anda untuk periode {periode_mulai} - {periode_selesai} telah tersedia. Silakan periksa.', # <-- DIUBAH
        'placeholders': '{nama_karyawan}, {periode_mulai}, {periode_selesai}',
    },
    {
        'event_trigger': 'SHIFT_UPDATED', # <-- DIUBAH
        'description': 'Info saat ada perubahan pada jadwal shift karyawan',
        'title_template': '🔄 Perubahan Jadwal Shift', # <-- DIUBAH
        'body_template': 'Perhatian, shift Anda pada tanggal {tanggal_shift} diubah menjadi {nama_shift} ({jam_masuk} - {jam_pulang}).', # <-- DIUBAH
        'placeholders': '{nama_karyawan}, {tanggal_shift}, {nama_shift}, {jam_masuk}, {jam_pulang}',
    },
    {
        'event_trigger': 'SHIFT_REMINDER_H1', # <-- DIUBAH
        'description': 'Pengingat H-1 sebelum jadwal shift karyawan',
        'title_template': '📢 Pengingat Shift Besok', # <-- DIUBAH
        'body_template': 'Jangan lupa, besok Anda masuk kerja pada shift {nama_shift} pukul {jam_masuk}.', # <-- DIUBAH
        'placeholders': '{nama_karyawan}, {nama_shift}, {jam_masuk}',
    },

    # --- Absensi (BARU) ---
    {
        'event_trigger': 'SUCCESS_CHECK_IN', # <-- DIUBAH
        'description': 'Konfirmasi saat karyawan berhasil melakukan check-in, menyertakan status (tepat/terlambat)',
        'title_template': '✅ Check-in Berhasil', # <-- DIUBAH
        'body_template': 'Absensi masuk Anda telah tercatat pada {jam_masuk} dengan status: {status_absensi}.', # <-- DIUBAH
        'placeholders': '{jam_masuk}, {status_absensi}, {nama_karyawan}',
    },
    {
        'event_trigger': 'SUCCESS_CHECK_OUT', # <-- DIUBAH
        'description': 'Konfirmasi saat karyawan berhasil melakukan check-out',
        'title_template': '👋 Sampai Jumpa!', # <-- DIUBAH
        'body_template': 'Absensi pulang Anda telah tercatat pada {jam_pulang}. Total durasi kerja Anda: {total_jam_kerja}.', # <-- DIUBAH
        'placeholders': '{jam_pulang}, {total_jam_kerja}, {nama_karyawan}',
    },

    # --- Agenda Kerja ---
    {
        'event_trigger': 'NEW_AGENDA_ASSIGNED', # <-- DIUBAH
        'description': 'Notifikasi saat karyawan diberikan agenda kerja baru',
        'title_template': '✍️ Agenda Kerja Baru', # <-- DIUBAH
        'body_template': 'Anda mendapatkan tugas baru: "{judul_agenda}". Batas waktu pengerjaan hingga {tanggal_deadline}.', # <-- DIUBAH
        'placeholders': '{nama_karyawan}, {judul_agenda}, {tanggal_deadline}, {pemberi_tugas}',
    },
    {
        'event_trigger': 'AGENDA_REMINDER_H1', # <-- DIUBAH
        'description': 'Pengingat H-1 sebelum deadline agenda kerja',
        'title_template': '🔔 Pengingat Agenda Kerja', # <-- DIUBAH
        'body_template': 'Jangan lupa, agenda "{judul_agenda}" akan jatuh tempo besok. Segera perbarui statusnya.', # <-- DIUBAH
        'placeholders': '{nama_karyawan}, {judul_agenda}',
    },
    {
        'event_trigger': 'AGENDA_OVERDUE', # <-- DIUBAH
        'description': 'Notifikasi saat agenda kerja melewati batas waktu',
        'title_template': '⏰ Agenda Melewati Batas Waktu', # <-- DIUBAH
        'body_template': 'Perhatian, agenda kerja "{judul_agenda}" telah melewati batas waktu pengerjaan.', # <-- DIUBAH
        'placeholders': '{nama_karyawan}, {judul_agenda}',
    },
    {
        'event_trigger': 'AGENDA_COMMENTED', # <-- DIUBAH
        'description': 'Notifikasi saat atasan/rekan memberi komentar pada agenda',
        'title_template': '💬 Komentar Baru pada Agenda', # <-- DIUBAH
        'body_template': '{nama_komentator} memberikan komentar pada agenda "{judul_agenda}". Silakan periksa detailnya.', # <-- DIUBAH
        'placeholders': '{nama_karyawan}, {judul_agenda}, {nama_komentator}',
    },

    # --- Kunjungan Klien (Dipertahankan dari List Awal karena Unik) ---
    {
        'event_trigger': 'NEW_CLIENT_VISIT_ASSIGNED', # <-- DIUBAH
        'description': 'Notifikasi saat karyawan mendapatkan jadwal kunjungan klien baru',
        'title_template': '🗓️ Kunjungan Klien Baru', # <-- DIUBAH
        'body_template': 'Anda dijadwalkan untuk kunjungan {kategori_kunjungan} pada {tanggal_kunjungan_display} {rentang_waktu_display}. Mohon persiapkan kebutuhan kunjungan.', # <-- DIUBAH
        'placeholders': '{nama_karyawan}, {kategori_kunjungan}, {tanggal_kunjungan}, {tanggal_kunjungan_display}, {rentang_waktu_display}',
    },
    {
        'event_trigger': 'CLIENT_VISIT_UPDATED', # <-- DIUBAH
        'description': 'Notifikasi saat detail kunjungan klien diperbarui',
        'title_template': 'ℹ️ Pembaruan Kunjungan Klien', # <-- DIUBAH
        'body_template': 'Detail kunjungan {kategori_kunjungan} pada {tanggal_kunjungan_display} telah diperbarui. Status terbaru: {status_kunjungan_display}.', # <-- DIUBAH
        'placeholders': '{nama_karyawan}, {kategori_kunjungan}, {tanggal_kunjungan_display}, {status_kunjungan_display}',
    },
    {
        'event_trigger': 'CLIENT_VISIT_REMINDER_END', # <-- DIUBAH
        'description': 'Pengingat saat kunjungan klien mendekati waktu selesai',
        'title_template': '⏳ Kunjungan Klien Hampir Selesai', # <-- DIUBAH
        'body_template': 'Kunjungan {kategori_kunjungan} pada {tanggal_kunjungan_display} akan berakhir pada {waktu_selesai_display}. Mohon lengkapi laporan kunjungan.', # <-- DIUBAH
        'placeholders': '{nama_karyawan}, {kategori_kunjungan}, {tanggal_kunjungan_display}, {waktu_selesai_display}',
    },

    # --- Istirahat ---
    {
        'event_trigger': 'SUCCESS_START_BREAK', # <-- DIUBAH
        'description': 'Konfirmasi saat karyawan memulai istirahat',
        'title_template': '☕ Istirahat Dimulai', # <-- DIUBAH
        'body_template': 'Anda memulai istirahat pada pukul {waktu_mulai_istirahat}. Selamat menikmati waktu istirahat Anda!', # <-- DIUBAH
        'placeholders': '{nama_karyawan}, {waktu_mulai_istirahat}',
    },
    {
        'event_trigger': 'SUCCESS_END_BREAK', # <-- DIUBAH
        'description': 'Konfirmasi saat karyawan mengakhiri istirahat',
        'title_template': '✅ Istirahat Selesai', # <-- DIUBAH
        'body_template': 'Anda telah mengakhiri istirahat pada pukul {waktu_selesai_istirahat}. Selamat melanjutkan pekerjaan!', # <-- DIUBAH
        'placeholders': '{nama_karyawan}, {waktu_selesai_istirahat}',
    },
    {
        'event_trigger': 'BREAK_TIME_EXCEEDED', # <-- DIUBAH
        'description': 'Notifikasi jika durasi istirahat melebihi batas',
        'title_template': '❗ Waktu Istirahat Berlebih', # <-- DIUBAH
        'body_template': 'Perhatian, durasi istirahat Anda telah melebihi batas maksimal {maks_jam_istirahat} menit yang ditentukan.', # <-- DIUBAH
        'placeholders': '{nama_karyawan}, {maks_jam_istirahat}',
    },
]


def ensure_notification_template_schema(session) -> None:
    """Pastikan tabel notification_templates memiliki skema terbaru."""

    inspector = inspect(session.bind)

    try:
        # Periksa kolom yang ada pada tabel notification_templates. Jika tabel belum
        # tersedia akan dilempar NoSuchTableError.
        existing_columns = {
            column["name"] for column in inspector.get_columns("notification_templates")
        }
    except NoSuchTableError:
        # Tabel belum dibuat, buat tabel baru dari definisi model
        print("Tabel notification_templates belum ada. Membuat tabel...")
        NotificationTemplate.__table__.create(session.bind, checkfirst=True)
        session.commit()
        existing_columns = {
            column.name for column in NotificationTemplate.__table__.columns
        }

    # -- Penanganan skema lama --
    # Dalam beberapa versi sebelumnya kolom bernama 'eventTrigger' (camelCase) digunakan
    # dan terdapat indeks unik pada kolom tersebut (notification_templates_eventTrigger_key).
    # Untuk memastikan skema konsisten kami perlu memindahkan nilai ke kolom baru
    # 'event_trigger' (snake_case) dan menghapus kolom serta indeks lama.
    if "eventTrigger" in existing_columns and "event_trigger" not in existing_columns:
        # Hanya ada kolom eventTrigger, ubah nama kolom tersebut menjadi event_trigger
        print("Menyesuaikan kolom legacy 'eventTrigger' menjadi 'event_trigger'...")
        session.execute(
            text(
                "ALTER TABLE notification_templates "
                "CHANGE COLUMN eventTrigger event_trigger VARCHAR(64) NULL DEFAULT NULL"
            )
        )
        session.commit()
        existing_columns.remove("eventTrigger")
        existing_columns.add("event_trigger")

    elif "eventTrigger" in existing_columns and "event_trigger" in existing_columns:
        # Kedua kolom ada; salin nilai dari eventTrigger ke event_trigger jika kolom baru kosong
        print(
            "Menyalin nilai dari kolom legacy 'eventTrigger' ke 'event_trigger' jika diperlukan..."
        )
        session.execute(
            text(
                "UPDATE notification_templates "
                "SET event_trigger = eventTrigger "
                "WHERE (event_trigger IS NULL OR event_trigger = '') "
                "AND eventTrigger IS NOT NULL AND eventTrigger <> ''"
            )
        )
        session.commit()
        print("Menghapus kolom legacy 'eventTrigger' yang sudah tidak digunakan...")
        session.execute(
            text("ALTER TABLE notification_templates DROP COLUMN eventTrigger")
        )
        session.commit()
        existing_columns.remove("eventTrigger")

    # Hapus indeks unik lama pada kolom eventTrigger jika masih ada
    indexes = {index["name"] for index in inspector.get_indexes("notification_templates")}
    if "notification_templates_eventTrigger_key" in indexes:
        print("Menghapus indeks unik lama 'notification_templates_eventTrigger_key'...")
        session.execute(
            text(
                "ALTER TABLE notification_templates DROP INDEX notification_templates_eventTrigger_key"
            )
        )
        session.commit()
        indexes.remove("notification_templates_eventTrigger_key")

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
            print(
                f"Kolom '{column_name}' belum ada. Menambahkan ke tabel notification_templates..."
            )
            session.execute(text(ddl))
            session.commit()
            existing_columns.add(column_name)

    indexes = {
        index["name"] for index in inspector.get_indexes("notification_templates")
    }
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
            # Baris ini sekarang tidak menyebabkan KeyError karena
            # kita sudah mengubah kunci di `notification_templates` menjadi 'event_trigger'
            stmt = select(NotificationTemplate).where(
                NotificationTemplate.event_trigger == template_data["event_trigger"]
            )
            exists = session.execute(stmt).scalar_one_or_none()

            if not exists:
                # Karena semua kunci sekarang snake_case, `**template_data` akan bekerja
                # dengan benar saat memanggil constructor model.
                template = NotificationTemplate(**template_data)
                session.add(template)
                print(f"Template dibuat: {template_data['event_trigger']}")
            else:
                # Semua lookup di sini juga menggunakan kunci snake_case
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