# flask_api_face/app/blueprints/absensi/routes.py

from datetime import datetime, date as _date
from flask import Blueprint, request, current_app
from sqlalchemy.exc import IntegrityError
from ...utils.responses import ok, error
from ...utils.geo import haversine_m
from ...utils.timez import now_local, today_local_date
from ...services.face_service import verify_user
from ...db import get_session
from ...db.models import (
    Location,
    Absensi,
    AbsensiStatus,
    AgendaKerja,
    AbsensiReportRecipient,
    ReportStatus,
    AtasanRole,
    Role,
    User,
    Catatan,
    ShiftKerja,
    PolaKerja,
    Istirahat,  # <-- Tambahkan import model Istirahat
)
        
absensi_bp = Blueprint("absensi", __name__) 

# ---------- helpers (tidak ada perubahan di sini) ----------
def _get_radius(loc: Location) -> int:
    r = loc.radius if loc and loc.radius is not None else current_app.config.get("DEFAULT_GEOFENCE_RADIUS", 100)
    try:
        return int(r)
    except Exception:
        return 100

# ... (helper lainnya tetap sama) ...

def _extract_agenda_kerja_ids(req) -> list[str]:
    """
    Ambil banyak field 'agenda_kerja_id' (multipart), bersihkan & unikkan.
    Setiap nilai harus berupa UUID string dari tabel agenda_kerja.id_agenda_kerja.
    """
    ids = req.form.getlist("agenda_kerja_id")
    seen, cleaned = set(), []
    for x in ids:
        x = (x or "").strip()
        if x and x not in seen:
            cleaned.append(x)
            seen.add(x)
    max_items = int(current_app.config.get("MAX_AGENDA_LINK_PER_REQUEST", 50))
    return cleaned[:max_items]

def _extract_recipients(req) -> list[str]:
    """
    Ambil banyak field 'recipient' (multipart) berisi id_user yang dituju.
    """
    ids = req.form.getlist("recipient")
    seen, cleaned = set(), []
    for x in ids:
        x = (x or "").strip()
        if x and x not in seen:
            cleaned.append(x)
            seen.add(x)
    max_rcp = int(current_app.config.get("MAX_RECIPIENTS_PER_REQUEST", 20))
    return cleaned[:max_rcp]

def _extract_catatan_entries(req) -> list[dict[str, str | None]]:
    """Kumpulkan pasangan deskripsi dan lampiran dari permintaan multipart."""
    descs = req.form.getlist("deskripsi_catatan")
    urls = req.form.getlist("lampiran_url")
    max_items = int(current_app.config.get("MAX_CATATAN_PER_REQUEST", 20))

    entries: list[dict[str, str | None]] = []
    total = max(len(descs), len(urls))
    for idx in range(total):
        desc_raw = descs[idx] if idx < len(descs) else ""
        url_raw = urls[idx] if idx < len(urls) else ""
        desc = (desc_raw or "").strip()
        if not desc:
            continue
        url = (url_raw or "").strip() or None
        entries.append(
            {
                "deskripsi_catatan": desc,
                "lampiran_url": url,
            }
        )
        if len(entries) >= max_items:
            break
    return entries

def _map_to_atasan_role(user: User) -> AtasanRole | None:
    """
    Snapshot role penerima sesuai enum AtasanRole (HR/OPERASIONAL/DIREKTUR).
    Jika user KARYAWAN atau tidak ada, kembalikan None (sesuai schema).
    """
    if not user or not user.role:
        return None
    if user.role == Role.HR:
        return AtasanRole.HR
    if user.role == Role.OPERASIONAL:
        return AtasanRole.OPERASIONAL
    if user.role == Role.DIREKTUR:
        return AtasanRole.DIREKTUR
    return None

def _link_agendas_to_absensi(session, user_id: str, absensi_id: str, agenda_ids: list[str]) -> tuple[int, int]:
    """
    Tautkan daftar AgendaKerja ke absensi (mengisi kolom id_absensi).
    Hanya memproses agenda milik user tersebut. Tidak menimpa jika sudah tertaut.
    return: (updated_count, skipped_count)
    """
    if not agenda_ids:
        return 0, 0

    rows = (
        session.query(AgendaKerja)
        .filter(AgendaKerja.id_agenda_kerja.in_(agenda_ids))
        .all()
    )

    updated, skipped = 0, 0
    for ag in rows:
        if ag.id_user != user_id:
            skipped += 1
            continue
        if ag.id_absensi is None:
            ag.id_absensi = absensi_id
            updated += 1
        else:
            skipped += 1
    return updated, skipped

# --- PERBAIKAN: Helper ini dimodifikasi agar bisa mengembalikan ID saja ---
def _agendas_payload_for_absensi(session, absensi_id: str, id_only: bool = False) -> list:
    """Ambil semua agenda_kerja yang sudah tertaut ke absensi tertentu."""
    rows = (
        session.query(AgendaKerja)
        .filter(AgendaKerja.id_absensi == absensi_id)
        .order_by(AgendaKerja.created_at.asc())
        .all()
    )
    
    if id_only:
        return [r.id_agenda_kerja for r in rows]

    out: list[dict] = []
    for r in rows:
        out.append(
            {
                "id_agenda_kerja": r.id_agenda_kerja,
                "id_agenda": r.id_agenda,
                "deskripsi_kerja": r.deskripsi_kerja,
                "start_date": r.start_date.isoformat() if getattr(r, "start_date", None) else None,
                "end_date": r.end_date.isoformat() if getattr(r, "end_date", None) else None,
                "status": r.status.value if r.status else None,
            }
        )
    return out


# ---------- routes absensi (checkin/checkout/status) ----------

@absensi_bp.post("/api/absensi/checkin")
def checkin():
    user_id = (request.form.get("user_id") or "").strip()
    loc_id = (request.form.get("location_id") or "").strip()
    lat = request.form.get("lat", type=float)
    lng = request.form.get("lng", type=float)
    f = request.files.get("image")
    agenda_ids = _extract_agenda_kerja_ids(request)
    recipients = _extract_recipients(request)
    catatan_entries = _extract_catatan_entries(request)

    metric = "cosine"
    threshold = 0.45

    if not user_id:
        return error("user_id wajib ada", 400)
    if lat is None or lng is None:
        return error("lat/lng wajib ada", 400)
    if f is None:
        return error("field 'image' wajib ada", 400)

    with get_session() as s:
        try:
            loc = s.get(Location, loc_id) if loc_id else None
            if loc_id and loc is None:
                return error("Lokasi tidak ditemukan", 404)

            dist = None
            if loc:
                dist = haversine_m(lng, lat, float(loc.longitude), float(loc.latitude))
                radius = _get_radius(loc)
                if dist > radius:
                    return error(f"Di luar geofence (jarak {int(dist)} m > radius {int(radius)} m)", 400)

            # --- PERBAIKAN 1: BUNGKUS VERIFIKASI WAJAH DALAM TRY-EXCEPT ---
            try:
                v = verify_user(user_id, f, metric=metric, threshold=threshold)
                if not v.get("match", False):
                    # --- PERBAIKAN 2: UBAH STATUS 401 MENJADI 400 ---
                    return error("Verifikasi wajah gagal. Tidak dapat check-in.", 400)
            except Exception as e:
                # Tangkap error lain dari service (misal: file tidak ditemukan)
                return error(f"Gagal melakukan verifikasi wajah: {str(e)}", 500)

            today = today_local_date()
            now_dt = now_local().replace(tzinfo=None, microsecond=0)

            # --- Logika penentuan status masuk ---
            status_kehadiran = AbsensiStatus.tepat
            HARI_MAP = {0: "SENIN", 1: "SELASA", 2: "RABU", 3: "KAMIS", 4: "JUMAT", 5: "SABTU", 6: "MINGGU"}
            nama_hari_ini = HARI_MAP.get(today.weekday())

            jadwal_kerja = None
            if nama_hari_ini:
                jadwal_kerja = s.query(ShiftKerja).join(PolaKerja).filter(
                    ShiftKerja.id_user == user_id,
                    ShiftKerja.tanggal_mulai <= today,
                    ShiftKerja.tanggal_selesai >= today,
                    ShiftKerja.hari_kerja.contains(nama_hari_ini)
                ).first()

            if jadwal_kerja and jadwal_kerja.polaKerja and jadwal_kerja.polaKerja.jam_mulai:
                jam_masuk_seharusnya = jadwal_kerja.polaKerja.jam_mulai.time()
                jam_checkin_aktual = now_dt.time()
                if jam_checkin_aktual > jam_masuk_seharusnya:
                    status_kehadiran = AbsensiStatus.terlambat
            
            rec = Absensi(
                id_user=user_id,
                face_verified_masuk=True,
                face_verified_pulang=False,
                tanggal=today,
                id_lokasi_datang=loc.id_location if loc else None,
                jam_masuk=now_dt,
                status_masuk=status_kehadiran,
                in_latitude=lat,
                in_longitude=lng,
            )
            s.add(rec)
            
            s.flush()  # dapatkan rec.id_absensi

            catatan_payload: list[dict[str, str | None]] = []
            if catatan_entries:
                catatan_rows: list[Catatan] = []
                for entry in catatan_entries:
                    row = Catatan(
                        id_absensi=rec.id_absensi,
                        deskripsi_catatan=entry["deskripsi_catatan"],
                        lampiran_url=entry["lampiran_url"],
                    )
                    s.add(row)
                    catatan_rows.append(row)
                s.flush()
                catatan_payload = [{"id_catatan": row.id_catatan, "deskripsi_catatan": row.deskripsi_catatan, "lampiran_url": row.lampiran_url} for row in catatan_rows]

            linked_count, skipped_count = _link_agendas_to_absensi(s, user_id, rec.id_absensi, agenda_ids)

            added_rcp = 0
            if recipients:
                existing = {r[0] for r in s.query(AbsensiReportRecipient.id_user).filter(AbsensiReportRecipient.id_absensi == rec.id_absensi).all()}
                for rid in recipients:
                    if rid in existing: continue
                    u = s.get(User, rid)
                    if u is None: continue
                    s.add(AbsensiReportRecipient(id_absensi=rec.id_absensi, id_user=rid, recipient_nama_snapshot=u.nama_pengguna, recipient_role_snapshot=_map_to_atasan_role(u), status=ReportStatus.terkirim))
                    added_rcp += 1

            s.commit()

            return ok(
                mode="checkin",
                distanceMeters=dist,
                agendasLinked=linked_count,
                agendasSkipped=skipped_count,
                recipientsAdded=added_rcp,
                catatan=catatan_payload,
                **v,
            )
        except IntegrityError:
            s.rollback()
            return error("Check-in duplikat untuk tanggal ini (sudah check-in).", 409)
        except Exception as e:
            s.rollback()
            return error(f"Terjadi kesalahan internal: {str(e)}", 500)


@absensi_bp.post("/api/absensi/checkout")
def checkout():
    user_id = (request.form.get("user_id") or "").strip()
    loc_id = (request.form.get("location_id") or "").strip()
    lat = request.form.get("lat", type=float)
    lng = request.form.get("lng", type=float)
    f = request.files.get("image")
    agenda_ids = _extract_agenda_kerja_ids(request)
    recipients = _extract_recipients(request)
    catatan_entries = _extract_catatan_entries(request)

    metric = "cosine"
    threshold = 0.45

    if not user_id:
        return error("user_id wajib ada", 400)
    if lat is None or lng is None:
        return error("lat/lng wajib ada", 400)
    if f is None:
        return error("field 'image' wajib ada", 400)

    with get_session() as s:
        try:
            today = today_local_date()
            rec = s.query(Absensi).filter(Absensi.id_user == user_id, Absensi.tanggal == today).one_or_none()

            if rec is None:
                return error("Belum ada check-in untuk hari ini.", 404)

            loc = s.get(Location, loc_id) if loc_id else None
            if loc_id and loc is None:
                return error("Lokasi tidak ditemukan", 404)

            dist = None
            if loc:
                dist = haversine_m(lng, lat, float(loc.longitude), float(loc.latitude))
                radius = _get_radius(loc)
                if dist > radius:
                    return error(f"Di luar geofence (jarak {int(dist)} m > radius {int(radius)} m)", 400)

            try:
                v = verify_user(user_id, f, metric=metric, threshold=threshold)
                if not v.get("match", False):
                    return error("Verifikasi wajah gagal. Tidak dapat check-out.", 400)
            except Exception as e:
                return error(f"Gagal melakukan verifikasi wajah: {str(e)}", 500)

            now_dt = now_local().replace(tzinfo=None, microsecond=0)
            rec.jam_pulang = now_dt
            rec.id_lokasi_pulang = loc.id_location if loc else None
            rec.out_latitude = lat
            rec.out_longitude = lng
            rec.face_verified_pulang = True

            existing_catatan = s.query(Catatan).filter(Catatan.id_absensi == rec.id_absensi).order_by(Catatan.id_catatan.asc()).all()
            kept_rows: list[Catatan] = []

            if catatan_entries:
                for idx, entry in enumerate(catatan_entries):
                    if idx < len(existing_catatan):
                        row = existing_catatan[idx]
                        row.deskripsi_catatan = entry["deskripsi_catatan"]
                        row.lampiran_url = entry["lampiran_url"]
                    else:
                        row = Catatan(id_absensi=rec.id_absensi, deskripsi_catatan=entry["deskripsi_catatan"], lampiran_url=entry["lampiran_url"])
                        s.add(row)
                    kept_rows.append(row)
                for row in existing_catatan[len(catatan_entries):]:
                    s.delete(row)
            else:
                kept_rows = list(existing_catatan)
            
            s.flush()

            catatan_payload = [{"id_catatan": row.id_catatan, "deskripsi_catatan": row.deskripsi_catatan, "lampiran_url": row.lampiran_url} for row in kept_rows]
            
            linked_count, skipped_count = _link_agendas_to_absensi(s, user_id, rec.id_absensi, agenda_ids)
            agendas_payload = _agendas_payload_for_absensi(s, rec.id_absensi)

            added_rcp = 0
            if recipients:
                existing = {r[0] for r in s.query(AbsensiReportRecipient.id_user).filter(AbsensiReportRecipient.id_absensi == rec.id_absensi).all()}
                for rid in recipients:
                    if rid in existing: continue
                    u = s.get(User, rid)
                    if u is None: continue
                    s.add(AbsensiReportRecipient(id_absensi=rec.id_absensi, id_user=rid, recipient_nama_snapshot=u.nama_pengguna, recipient_role_snapshot=_map_to_atasan_role(u), status=ReportStatus.terkirim))
                    added_rcp += 1

            s.commit()

            return ok(
                mode="checkout",
                distanceMeters=dist,
                jam_pulang=rec.jam_pulang.isoformat() if rec.jam_pulang else None,
                agendasLinked=linked_count,
                agendasSkipped=skipped_count,
                recipientsAdded=added_rcp,
                catatan=catatan_payload,
                agendas=agendas_payload,
                **v,
            )
        except Exception as e:
            s.rollback()
            return error(f"Terjadi kesalahan internal saat checkout: {str(e)}", 500)


@absensi_bp.get("/api/absensi/status")
def absensi_status():
    user_id = (request.args.get("user_id") or "").strip()
    if not user_id:
        return error("user_id wajib ada", 400)

    with get_session() as s:
        today = today_local_date()
        rec = s.query(Absensi).filter(
            Absensi.id_user == user_id,
            Absensi.tanggal == today
        ).one_or_none()

        if rec is None:
            return ok(mode="checkin", today=str(today), jam_masuk=None, jam_pulang=None, linked_agenda_ids=[])

        # --- PERBAIKAN: Ambil ID agenda yang sudah tertaut ---
        linked_ids = _agendas_payload_for_absensi(s, rec.id_absensi, id_only=True)

        if rec.jam_pulang is None:
            return ok(
                mode="checkout",
                today=str(today),
                jam_masuk=rec.jam_masuk.isoformat() if rec.jam_masuk else None,
                jam_pulang=None,
                linked_agenda_ids=linked_ids,
            )

        return ok(
            mode="done",
            today=str(today),
            jam_masuk=rec.jam_masuk.isoformat() if rec.jam_masuk else None,
            jam_pulang=rec.jam_pulang.isoformat() if rec.jam_pulang else None,
            linked_agenda_ids=linked_ids,
        )

# --- ENDPOINT BARU UNTUK FITUR ISTIRAHAT ---

@absensi_bp.post("/api/absensi/istirahat/start")
def start_istirahat():
    user_id = (request.form.get("user_id") or "").strip()
    lat = request.form.get("start_istirahat_latitude", type=float)
    lng = request.form.get("start_istirahat_longitude", type=float)
    
    if not user_id:
        return error("user_id wajib ada", 400)
    if lat is None or lng is None:
        return error("Koordinat latitude dan longitude wajib ada", 400)

    with get_session() as s:
        try:
            today = today_local_date()
            absensi = s.query(Absensi).filter(
                Absensi.id_user == user_id,
                Absensi.tanggal == today
            ).one_or_none()

            if absensi is None or absensi.jam_masuk is None:
                return error("Anda harus check-in terlebih dahulu sebelum memulai istirahat", 400)
            if absensi.jam_pulang is not None:
                return error("Tidak dapat memulai istirahat setelah check-out", 400)

            # Cek apakah sudah ada istirahat yang berjalan
            existing_break = s.query(Istirahat).filter(
                Istirahat.id_absensi == absensi.id_absensi,
                Istirahat.end_istirahat.is_(None)
            ).first()
            if existing_break:
                return error("Anda sudah dalam sesi istirahat", 409)

            now_dt = now_local().replace(tzinfo=None)

            # Validasi jadwal istirahat
            jadwal_kerja = s.query(ShiftKerja).join(PolaKerja).filter(
                ShiftKerja.id_user == user_id,
                ShiftKerja.tanggal_mulai <= today,
                ShiftKerja.tanggal_selesai >= today
            ).first()

            if jadwal_kerja and jadwal_kerja.polaKerja:
                pola = jadwal_kerja.polaKerja
                if pola.jam_istirahat_mulai and pola.jam_istirahat_selesai:
                    jam_mulai_seharusnya = pola.jam_istirahat_mulai.time()
                    jam_selesai_seharusnya = pola.jam_istirahat_selesai.time()
                    jam_sekarang = now_dt.time()
                    if not (jam_mulai_seharusnya <= jam_sekarang <= jam_selesai_seharusnya):
                        return error(f"Waktu istirahat hanya diizinkan antara {jam_mulai_seharusnya.strftime('%H:%M')} dan {jam_selesai_seharusnya.strftime('%H:%M')}", 403)

            new_break = Istirahat(
                id_user=user_id,
                id_absensi=absensi.id_absensi,
                tanggal_istirahat=today,
                start_istirahat=now_dt,
                start_istirahat_latitude=lat,
                start_istirahat_longitude=lng
            )
            s.add(new_break)
            s.commit()
            s.refresh(new_break)

            return ok(
                message="Sesi istirahat dimulai",
                id_istirahat=new_break.id_istirahat,
                start_istirahat=new_break.start_istirahat.isoformat()
            )

        except Exception as e:
            s.rollback()
            return error(f"Terjadi kesalahan: {str(e)}", 500)

@absensi_bp.post("/api/absensi/istirahat/end")
def end_istirahat():
    user_id = (request.form.get("user_id") or "").strip()
    lat = request.form.get("end_istirahat_latitude", type=float)
    lng = request.form.get("end_istirahat_longitude", type=float)

    if not user_id:
        return error("user_id wajib ada", 400)
    if lat is None or lng is None:
        return error("Koordinat latitude dan longitude wajib ada", 400)
        
    with get_session() as s:
        try:
            today = today_local_date()
            absensi = s.query(Absensi).filter(
                Absensi.id_user == user_id,
                Absensi.tanggal == today
            ).one_or_none()

            if absensi is None:
                return error("Absensi hari ini tidak ditemukan", 404)

            current_break = s.query(Istirahat).filter(
                Istirahat.id_absensi == absensi.id_absensi,
                Istirahat.end_istirahat.is_(None)
            ).one_or_none()

            if current_break is None:
                return error("Tidak ada sesi istirahat yang sedang berjalan", 404)

            now_dt = now_local().replace(tzinfo=None)
            current_break.end_istirahat = now_dt
            current_break.end_istirahat_latitude = lat
            current_break.end_istirahat_longitude = lng
            
            s.commit()

            duration = (now_dt - current_break.start_istirahat).total_seconds()

            return ok(
                message="Sesi istirahat selesai",
                id_istirahat=current_break.id_istirahat,
                end_istirahat=now_dt.isoformat(),
                duration_seconds=int(duration)
            )

        except Exception as e:
            s.rollback()
            return error(f"Terjadi kesalahan: {str(e)}", 500)

@absensi_bp.get("/api/absensi/istirahat/status")
def istirahat_status():
    user_id = (request.args.get("user_id") or "").strip()
    if not user_id:
        return error("user_id wajib ada", 400)

    with get_session() as s:
        today = today_local_date()
        
        # Cari sesi istirahat yang aktif hari ini
        active_break = s.query(Istirahat).join(Absensi).filter(
            Absensi.id_user == user_id,
            Istirahat.tanggal_istirahat == today,
            Istirahat.end_istirahat.is_(None)
        ).one_or_none()

        if active_break:
            duration = (now_local().replace(tzinfo=None) - active_break.start_istirahat).total_seconds()
            return ok(
                status="active",
                id_istirahat=active_break.id_istirahat,
                start_istirahat=active_break.start_istirahat.isoformat(),
                elapsed_seconds=int(duration)
            )

        # Jika tidak ada yang aktif, cek total durasi istirahat hari ini
        total_duration = 0
        all_breaks_today = s.query(Istirahat).join(Absensi).filter(
            Absensi.id_user == user_id,
            Istirahat.tanggal_istirahat == today,
            Istirahat.end_istirahat.isnot(None)
        ).all()

        for b in all_breaks_today:
            total_duration += (b.end_istirahat - b.start_istirahat).total_seconds()

        return ok(
            status="inactive",
            total_duration_seconds=int(total_duration)
        )