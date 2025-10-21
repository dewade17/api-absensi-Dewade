# app/tasks/absensi_tasks.py
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from datetime import date, datetime

from app.extensions import celery
from app.db import get_session
from app.db.models import (
    Absensi,
    User,
    Location,
    AgendaKerja,
    AbsensiReportRecipient,
    Catatan,
    ShiftKerja,
    PolaKerja,
    AbsensiStatus,
    ReportStatus,
    Role,
    AtasanRole,
)
from app.services.notification_service import send_notification
from app.utils.timez import now_local, today_local_date

logger = logging.getLogger(__name__)
logger.info("[absensi.tasks] loaded from %s", __file__)

def _map_to_atasan_role(user_role: Role) -> AtasanRole | None:
    if not user_role:
        return None
    if user_role == Role.HR:
        return AtasanRole.HR
    if user_role == Role.OPERASIONAL:
        return AtasanRole.OPERASIONAL
    if user_role == Role.DIREKTUR:
        return AtasanRole.DIREKTUR
    return None

@celery.task(name="absensi.healthcheck", bind=True)
def healthcheck(self) -> Dict[str, Any]:
    host = getattr(getattr(self, "request", None), "hostname", "unknown")
    logger.info("[absensi.healthcheck] OK from %s", host)
    return {"status": "ok", "host": host}

@celery.task(name="absensi.process_checkin_task_v2", bind=True)
def process_checkin_task_v2(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Proses check-in asynchronous.
    """
    logger.info("[process_checkin_task_v2] start payload=%s", payload)
    user_id = payload.get("user_id")
    today = date.fromisoformat(payload["today_local"])
    now_dt = datetime.fromisoformat(payload["now_local_iso"]).replace(tzinfo=None)
    location = payload.get("location", {})
    
    with get_session() as s:
        try:
            jadwal_kerja = s.query(ShiftKerja).join(PolaKerja).filter(
                ShiftKerja.id_user == user_id,
                ShiftKerja.tanggal_mulai <= today,
                ShiftKerja.tanggal_selesai >= today,
            ).first()

            # Variabel untuk Absensi Record
            status_kehadiran = AbsensiStatus.tepat
            
            # Variabel untuk Notifikasi (Default: Tepat Waktu)
            status_absensi_str = "Tepat Waktu"
            jam_masuk_str = now_dt.strftime("%H:%M")

            if jadwal_kerja and jadwal_kerja.polaKerja and jadwal_kerja.polaKerja.jam_mulai:
                jam_masuk_seharusnya = jadwal_kerja.polaKerja.jam_mulai.time()
                jam_checkin_aktual = now_dt.time()
                if jam_checkin_aktual > jam_masuk_seharusnya:
                    status_kehadiran = AbsensiStatus.terlambat
                    status_absensi_str = "Terlambat" # Update status string untuk notifikasi

            rec = Absensi(
                id_user=user_id,
                tanggal=today,
                jam_masuk=now_dt,
                status_masuk=status_kehadiran,
                id_lokasi_datang=location.get("id"),
                in_latitude=location.get("lat"),
                in_longitude=location.get("lng"),
                face_verified_masuk=True,
                face_verified_pulang=False,
            )
            s.add(rec)
            s.flush()
            
            absensi_id = rec.id_absensi
            logger.info(f"Absensi record created with id: {absensi_id}")

            agenda_ids = payload.get("agenda_ids", [])
            if agenda_ids:
                s.query(AgendaKerja).filter(
                    AgendaKerja.id_user == user_id,
                    AgendaKerja.id_agenda_kerja.in_(agenda_ids),
                    AgendaKerja.id_absensi.is_(None)
                ).update({"id_absensi": absensi_id}, synchronize_session=False)

            for entry in payload.get("catatan_entries", []):
                s.add(Catatan(id_absensi=absensi_id, **entry))

            recipient_ids = payload.get("recipients", [])
            if recipient_ids:
                recipients = s.query(User).filter(User.id_user.in_(recipient_ids)).all()
                for u in recipients:
                    s.add(AbsensiReportRecipient(
                        id_absensi=absensi_id,
                        id_user=u.id_user,
                        recipient_nama_snapshot=u.nama_pengguna,
                        recipient_role_snapshot=_map_to_atasan_role(u.role),
                        status=ReportStatus.terkirim,
                    ))

            s.commit()
            logger.info(f"[process_checkin_task_v2] SUCCESS for user_id={user_id}")
            
            # --- LOGIKA NOTIFIKASI CHECK-IN BERHASIL ---
            dynamic_data = {
                "jam_masuk": jam_masuk_str,
                "status_absensi": status_absensi_str,
                # Tambahkan 'nama_karyawan' jika User object diambil di awal task
            }
            
            send_notification(
                event_trigger="SUCCESS_CHECK_IN",
                user_id=user_id,
                dynamic_data=dynamic_data,
                session=s,
            )
            # --- END LOGIKA NOTIFIKASI CHECK-IN ---

            return {"status": "ok", "message": "Check-in berhasil disimpan", "absensi_id": absensi_id}

        except Exception as e:
            s.rollback()
            logger.exception("[process_checkin_task_v2] error: %s", e)
            return {"status": "error", "message": str(e)}

@celery.task(name="absensi.process_checkout_task_v2", bind=True)
def process_checkout_task_v2(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Proses check-out asynchronous.
    """
    logger.info("[process_checkout_task_v2] start payload=%s", payload)
    user_id = payload.get("user_id")
    absensi_id = payload.get("absensi_id")
    now_dt = datetime.fromisoformat(payload["now_local_iso"]).replace(tzinfo=None)
    location = payload.get("location", {})

    with get_session() as s:
        try:
            # 1. Ambil record absensi yang sudah ada
            rec = s.get(Absensi, absensi_id)
            if not rec:
                logger.error(f"Absensi record with id {absensi_id} not found for checkout.")
                return {"status": "error", "message": f"Absensi record {absensi_id} not found."}

            # 2. Update data checkout
            rec.jam_pulang = now_dt
            rec.id_lokasi_pulang = location.get("id")
            rec.out_latitude = location.get("lat")
            rec.out_longitude = location.get("lng")
            rec.face_verified_pulang = True
            
            # (Tambahkan logika status pulang jika perlu, misal pulang cepat)
            rec.status_pulang = AbsensiStatus.tepat

            # 3. Tautkan Agenda Kerja (jika ada yang baru)
            agenda_ids = payload.get("agenda_ids", [])
            if agenda_ids:
                s.query(AgendaKerja).filter(
                    AgendaKerja.id_user == user_id,
                    AgendaKerja.id_agenda_kerja.in_(agenda_ids),
                    AgendaKerja.id_absensi.is_(None)
                ).update({"id_absensi": absensi_id}, synchronize_session=False)

            # 4. Tambahkan Catatan baru
            for entry in payload.get("catatan_entries", []):
                s.add(Catatan(id_absensi=absensi_id, **entry))

            # 5. Tambahkan Penerima Laporan baru (jika ada)
            recipient_ids = payload.get("recipients", [])
            if recipient_ids:
                # Hindari duplikasi
                existing_recipients = s.query(AbsensiReportRecipient.id_user).filter_by(id_absensi=absensi_id).all()
                existing_ids = {r[0] for r in existing_recipients}
                new_ids = set(recipient_ids) - existing_ids
                
                if new_ids:
                    recipients = s.query(User).filter(User.id_user.in_(new_ids)).all()
                    for u in recipients:
                        s.add(AbsensiReportRecipient(
                            id_absensi=absensi_id,
                            id_user=u.id_user,
                            recipient_nama_snapshot=u.nama_pengguna,
                            recipient_role_snapshot=_map_to_atasan_role(u.role),
                            status=ReportStatus.terkirim,
                        ))

            s.commit()
            logger.info(f"[process_checkout_task_v2] SUCCESS for user_id={user_id}")
            
            # --- LOGIKA NOTIFIKASI CHECK-OUT BERHASIL (BARU) ---
            # Hitung total jam kerja (sederhana: jam pulang - jam masuk)
            total_duration = now_dt - rec.jam_masuk
            # Format ke string sederhana (misal: '8 jam 30 menit')
            total_jam_kerja = f"{total_duration.seconds // 3600} jam {total_duration.seconds % 3600 // 60} menit"
            jam_pulang_str = now_dt.strftime("%H:%M")
            
            dynamic_data = {
                "jam_pulang": jam_pulang_str,
                "total_jam_kerja": total_jam_kerja,
                # Tambahkan 'nama_karyawan' jika User object diambil di awal task
            }
            
            send_notification(
                event_trigger="SUCCESS_CHECK_OUT",
                user_id=user_id,
                dynamic_data=dynamic_data,
                session=s,
            )
            # --- END LOGIKA NOTIFIKASI CHECK-OUT ---
            
            return {"status": "ok", "message": "Check-out berhasil disimpan", "absensi_id": absensi_id}

        except Exception as e:
            s.rollback()
            logger.exception("[process_checkout_task_v2] error: %s", e)
            return {"status": "error", "message": str(e)}

# --- Alias kompatibilitas ---
process_checkin_task = process_checkin_task_v2
process_checkout_task = process_checkout_task_v2