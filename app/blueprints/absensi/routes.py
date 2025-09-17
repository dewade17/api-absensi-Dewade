# blueprints/absensi/routes.py
from datetime import datetime, date as _date
from flask import Blueprint, request, current_app
from sqlalchemy.exc import IntegrityError
from ...utils.responses import ok, error
from ...utils.geo import haversine_m
from ...utils.timez import now_local, today_local_date
from ...services.face_service import verify_user
from ...db import get_session
from ...db.models import (
    Catatan,
    Location,
    Absensi,
    AbsensiStatus,
    AgendaKerja,
    AbsensiReportRecipient,
    ReportStatus,
    AtasanRole,
    Role,
    User,
)

absensi_bp = Blueprint("absensi", __name__)

# ---------- helpers ----------
def _get_radius(loc: Location) -> int:
    r = loc.radius if loc and loc.radius is not None else current_app.config.get("DEFAULT_GEOFENCE_RADIUS", 100)
    try:
        return int(r)
    except Exception:
        return 100

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
    """
    Ambil pasangan deskripsi_catatan & lampiran_url (multipart) dari request.
    Hanya masukkan deskripsi yang tidak kosong. lampiran_url bersifat opsional.
    """
    descs = req.form.getlist("deskripsi_catatan")
    urls = req.form.getlist("lampiran_url")
    max_notes = int(current_app.config.get("MAX_CATATAN_PER_REQUEST", 10))

    notes: list[dict[str, str | None]] = []
    for idx, raw_desc in enumerate(descs):
        desc = (raw_desc or "").strip()
        if not desc:
            continue

        url = urls[idx] if idx < len(urls) else None
        cleaned_url = (url or "").strip() or None

        notes.append({
            "deskripsi_catatan": desc,
            "lampiran_url": cleaned_url,
        })

        if len(notes) >= max_notes:
            break

    return notes

def _map_to_atasan_role(user: User) -> AtasanRole | None:
    """
    Snapshot role penerima sesuai enum AtasanRole (HR/OPERASIONAL/DIREKTUR).
    Jika user KARYAWAN atau tidak ada, kembalikan None (sesuai schema prisma).
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

    # Ambil semua agenda yg relevan & milik user
    updated, skipped = 0, 0
    for ag in rows:
        if ag.id_user != user_id:
            skipped += 1
            continue
        if ag.id_absensi is None:
            ag.id_absensi = absensi_id
            updated += 1
        else:
            # sudah tertaut ke absensi (mungkin hari lain) -> skip
            skipped += 1
    return updated, skipped

# ---------- routes ----------
@absensi_bp.post("/api/absensi/checkin")
def checkin():
    user_id = (request.form.get("user_id") or "").strip()
    loc_id = (request.form.get("location_id") or "").strip()
    lat = request.form.get("lat", type=float)
    lng = request.form.get("lng", type=float)
    f = request.files.get("image")
    agenda_ids = _extract_agenda_kerja_ids(request)
    recipients = _extract_recipients(request)
    notes = _extract_catatan_entries(request)

    metric = "cosine"
    threshold = 0.45

    if not user_id:
        return error("user_id wajib ada", 400)
    if lat is None or lng is None:
        return error("lat/lng wajib ada", 400)
    if f is None:
        return error("field 'image' wajib ada", 400)

    with get_session() as s:
        loc = s.get(Location, loc_id) if loc_id else None
        if loc_id and loc is None:
            return error("Lokasi tidak ditemukan", 404)

        dist = None
        if loc:
            dist = haversine_m(lng, lat, float(loc.longitude), float(loc.latitude))
            radius = _get_radius(loc)
            if dist > radius:
                return error(f"Di luar geofence (jarak {int(dist)} m > radius {int(radius)} m)", 400)

        # Face verify
        v = verify_user(user_id, f, metric=metric, threshold=threshold)
        if not v.get("match", False):
            return error("Verifikasi wajah gagal. Tidak dapat check-in.", 401)

        today = today_local_date()
        now_dt = now_local().replace(tzinfo=None, microsecond=0)

        rec = Absensi(
            id_user=user_id,
            face_verified_masuk=True,
            face_verified_pulang=False,
            tanggal=today,
            id_lokasi_datang=loc.id_location if loc else None,
            jam_masuk=now_dt,
            status=AbsensiStatus.tepat,
            in_latitude=lat,
            in_longitude=lng,
        )
        s.add(rec)

        catatan_payload = None
        try:
            s.flush()  # dapatkan rec.id_absensi

            if notes:
                catatan_rows: list[Catatan] = []
                for entry in notes:
                    cat = Catatan(
                        id_absensi=rec.id_absensi,
                        deskripsi_catatan=entry["deskripsi_catatan"],
                        lampiran_url=entry["lampiran_url"],
                    )
                    s.add(cat)
                    catatan_rows.append(cat)

                s.flush()
                catatan_payload = [
                    {
                        "id_catatan": cat.id_catatan,
                        "deskripsi_catatan": cat.deskripsi_catatan,
                        "lampiran_url": cat.lampiran_url,
                    }
                    for cat in catatan_rows
                ]

            # Tautkan agenda_kerja -> absensi
            linked_count, skipped_count = _link_agendas_to_absensi(s, user_id, rec.id_absensi, agenda_ids)

            # Simpan penerima laporan (absensi_report_recipients)
            added_rcp = 0
            if recipients:
                existing = {
                    r[0]
                    for r in s.query(AbsensiReportRecipient.id_user)
                    .filter(AbsensiReportRecipient.id_absensi == rec.id_absensi)
                    .all()
                }

                for rid in recipients:
                    if rid in existing:
                        continue

                    u = s.get(User, rid)
                    s.add(
                        AbsensiReportRecipient(
                            id_absensi=rec.id_absensi,
                            id_user=rid,
                            recipient_role_snapshot=_map_to_atasan_role(u),
                            status=ReportStatus.terkirim,
                        )
                    )
                    added_rcp += 1

            s.commit()
        except IntegrityError:
            s.rollback()
            return error("Check-in duplikat untuk tanggal ini (sudah check-in).", 409)

        return ok(
            mode="checkin",
            distanceMeters=dist,
            agendasLinked=linked_count,
            agendasSkipped=skipped_count,
            recipientsAdded=added_rcp,
            catatan=catatan_payload,
            **v,
        )


@absensi_bp.post("/api/absensi/checkout")
def checkout():
    user_id = (request.form.get("user_id") or "").strip()
    loc_id = (request.form.get("location_id") or "").strip()
    lat = request.form.get("lat", type=float)
    lng = request.form.get("lng", type=float)
    f = request.files.get("image")
    agenda_ids = _extract_agenda_kerja_ids(request)
    recipients = _extract_recipients(request)
    notes = _extract_catatan_entries(request)

    metric = "cosine"
    threshold = 0.45

    if not user_id:
        return error("user_id wajib ada", 400)
    if lat is None or lng is None:
        return error("lat/lng wajib ada", 400)
    if f is None:
        return error("field 'image' wajib ada", 400)

    with get_session() as s:
        today = today_local_date()
        rec = s.query(Absensi).filter(
            Absensi.id_user == user_id,
            Absensi.tanggal == today
        ).one_or_none()

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

        # Face verify
        v = verify_user(user_id, f, metric=metric, threshold=threshold)
        if not v.get("match", False):
            return error("Verifikasi wajah gagal. Tidak dapat check-out.", 401)

        now_dt = now_local().replace(tzinfo=None, microsecond=0)
        rec.jam_pulang = now_dt
        rec.id_lokasi_pulang = loc.id_location if loc else None
        rec.out_latitude = lat
        rec.out_longitude = lng
        rec.face_verified_pulang = True

        catatan_payload = None
        if notes:
            existing_catatan = (
                s.query(Catatan)
                .filter(Catatan.id_absensi == rec.id_absensi)
                .order_by(Catatan.created_at.asc(), Catatan.id_catatan.asc())
                .all()
            )

            catatan_rows: list[Catatan] = []

            for idx, entry in enumerate(notes):
                if idx < len(existing_catatan):
                    cat = existing_catatan[idx]
                    cat.deskripsi_catatan = entry["deskripsi_catatan"]
                    cat.lampiran_url = entry["lampiran_url"]
                else:
                    cat = Catatan(
                        id_absensi=rec.id_absensi,
                        deskripsi_catatan=entry["deskripsi_catatan"],
                        lampiran_url=entry["lampiran_url"],
                    )
                    s.add(cat)
                catatan_rows.append(cat)

            # Hapus catatan yang tidak lagi dikirim
            for cat in existing_catatan[len(notes):]:
                s.delete(cat)

            s.flush()
            catatan_payload = [
                {
                    "id_catatan": cat.id_catatan,
                    "deskripsi_catatan": cat.deskripsi_catatan,
                    "lampiran_url": cat.lampiran_url,
                }
                for cat in catatan_rows
            ]

        # Tautkan agenda_kerja -> absensi (kalau ada yang dikirim saat checkout)
        linked_count, skipped_count = _link_agendas_to_absensi(s, user_id, rec.id_absensi, agenda_ids)

        # Simpan penerima laporan (absensi_report_recipients)
        added_rcp = 0
        if recipients:
            existing = {
                r[0]
                for r in s.query(AbsensiReportRecipient.id_user)
                .filter(AbsensiReportRecipient.id_absensi == rec.id_absensi)
                .all()
            }

            for rid in recipients:
                if rid in existing:
                    continue

                u = s.get(User, rid)
                s.add(
                    AbsensiReportRecipient(
                        id_absensi=rec.id_absensi,
                        id_user=rid,
                        recipient_role_snapshot=_map_to_atasan_role(u),
                        status=ReportStatus.terkirim,
                    )
                )
                added_rcp += 1

        s.commit()

        return ok(
            mode="checkout",
            distanceMeters=dist,
            agendasLinked=linked_count,
            agendasSkipped=skipped_count,
            recipientsAdded=added_rcp,
            catatan=catatan_payload,
            **v,
        )

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
            # Belum ada check-in hari ini
            return ok(mode="checkin", today=str(today), jam_masuk=None, jam_pulang=None)

        if rec.jam_pulang is None:
            # Sudah check-in, belum check-out
            return ok(
                mode="checkout",
                today=str(today),
                jam_masuk=rec.jam_masuk.isoformat() if rec.jam_masuk else None,
                jam_pulang=None,
            )

        # Sudah selesai keduanya
        return ok(
            mode="done",
            today=str(today),
            jam_masuk=rec.jam_masuk.isoformat() if rec.jam_masuk else None,
            jam_pulang=rec.jam_pulang.isoformat() if rec.jam_pulang else None,
        )
