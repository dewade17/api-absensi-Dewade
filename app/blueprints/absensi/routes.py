# flask_api_face/app/blueprints/absensi/routes.py

from __future__ import annotations

from datetime import datetime, date as _date, timezone
from flask import Blueprint, request, current_app
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from ...utils.responses import ok, error
from ...utils.geo import haversine_m
from ...utils.timez import now_local, today_local_date
from ...services.face_service import verify_user
from ...services.notification_service import send_notification
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
    Istirahat,
)

# >>> Import Celery tasks (ABSOLUTE import, stabil)
from app.blueprints.absensi.tasks import (
    process_checkin_task_v2,
    process_checkout_task_v2,
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

@absensi_bp.post("/checkin")
def checkin():
    """
    Verifikasi cepat + enqueue Celery task, balas 202.
    Client dapat mem-poll /api/absensi/status untuk progres hasil.
    """
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
        # Validasi lokasi & geofence (ringan)
        loc = s.get(Location, loc_id) if loc_id else None
        if loc_id and loc is None:
            return error("Lokasi tidak ditemukan", 404)

        dist = None
        if loc:
            # FIX: urutan haversine_m adalah (lat1, lon1, lat2, lon2)
            dist = haversine_m(lat, lng, float(loc.latitude), float(loc.longitude))
            radius = _get_radius(loc)
            if dist > radius:
                return error(f"Di luar geofence (jarak {int(dist)} m > radius {int(radius)} m)", 400)

        # Verifikasi wajah (ringan)
        try:
            v = verify_user(user_id, f, metric=metric, threshold=threshold)
            if not v.get("match", False):
                return error("Verifikasi wajah gagal. Tidak dapat check-in.", 400)
        except Exception as e:
            return error(f"Gagal melakukan verifikasi wajah: {str(e)}", 500)

        # Precheck duplikat agar balasan cepat bila sudah check-in
        today = today_local_date()
        already = (
            s.query(Absensi)
            .filter(Absensi.id_user == user_id, Absensi.tanggal == today)
            .one_or_none()
        )
        if already:
            return error("Check-in duplikat untuk tanggal ini (sudah check-in).", 409)

    # Susun payload untuk background task
    payload = {
        "user_id": user_id,
        "today_local": today.isoformat(),
        "now_local_iso": now_local().replace(microsecond=0).isoformat(),
        "location": {
            "id": loc_id or None,
            "lat": lat,
            "lng": lng,
            "distance_m": int(dist) if dist is not None else None,
        },
        "agenda_ids": agenda_ids,          # untuk ditautkan di worker
        "recipients": recipients,          # untuk AbsensiReportRecipient di worker
        "catatan_entries": catatan_entries # untuk Catatan di worker
    }

    # Enqueue Celery task (pakai v2)
    async_res = process_checkin_task_v2.delay(payload)
    return (
        ok(
            accepted=True,
            task_id=async_res.id,
            message="Check-in diterima, diproses di background",
            distanceMeters=(int(dist) if dist is not None else None),
            **v,  # propagasi info verifikasi wajah (mis. score/distance)
        ),
        202,
    )


@absensi_bp.post("/checkout")
def checkout():
    """
    Verifikasi cepat + enqueue Celery task, balas 202.
    Worker akan mengisi jam_pulang, memperbarui catatan/agendas/recipients, dan kirim notifikasi.
    """
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
        today = today_local_date()
        rec = (
            s.query(Absensi)
            .filter(Absensi.id_user == user_id, Absensi.tanggal == today)
            .one_or_none()
        )

        if rec is None:
            return error("Belum ada check-in untuk hari ini.", 404)

        loc = s.get(Location, loc_id) if loc_id else None
        if loc_id and loc is None:
            return error("Lokasi tidak ditemukan", 404)

        dist = None
        if loc:
            # FIX: urutan haversine_m adalah (lat1, lon1, lat2, lon2)
            dist = haversine_m(lat, lng, float(loc.latitude), float(loc.longitude))
            radius = _get_radius(loc)
            if dist > radius:
                return error(f"Di luar geofence (jarak {int(dist)} m > radius {int(radius)} m)", 400)

        try:
            v = verify_user(user_id, f, metric=metric, threshold=threshold)
            if not v.get("match", False):
                return error("Verifikasi wajah gagal. Tidak dapat check-out.", 400)
        except Exception as e:
            return error(f"Gagal melakukan verifikasi wajah: {str(e)}", 500)

        absensi_id = rec.id_absensi  # diperlukan worker untuk update baris yang sama

    # Payload checkout untuk worker
    payload = {
        "user_id": user_id,
        "absensi_id": absensi_id,
        "today_local": today.isoformat(),
        "now_local_iso": now_local().replace(microsecond=0).isoformat(),
        "location": {
            "id": loc_id or None,
            "lat": lat,
            "lng": lng,
            "distance_m": int(dist) if dist is not None else None,
        },
        "agenda_ids": agenda_ids,           # worker akan menautkan jika ada yg belum
        "recipients": recipients,           # worker akan tambah penerima laporan
        "catatan_entries": catatan_entries  # worker akan upsert urutannya
    }

    async_res = process_checkout_task_v2.delay(payload)
    return (
        ok(
            accepted=True,
            task_id=async_res.id,
            message="Check-out diterima, diproses di background",
            distanceMeters=(int(dist) if dist is not None else None),
            **v,
        ),
        202,
    )


@absensi_bp.get("/status")
def absensi_status():
    user_id = (request.args.get("user_id") or "").strip()
    if not user_id:
        return error("user_id wajib ada", 400)

    with get_session() as s:
        today = today_local_date()
        rec = (
            s.query(Absensi)
            .filter(Absensi.id_user == user_id, Absensi.tanggal == today)
            .one_or_none()
        )

        if rec is None:
            return ok(mode="checkin", today=str(today), jam_masuk=None, jam_pulang=None, linked_agenda_ids=[])

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


# --- FITUR ISTIRAHAT ---

@absensi_bp.post("/istirahat/start")
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
            absensi = (
                s.query(Absensi)
                .filter(Absensi.id_user == user_id, Absensi.tanggal == today)
                .one_or_none()
            )

            if absensi is None or absensi.jam_masuk is None:
                return error("Anda harus check-in terlebih dahulu sebelum memulai istirahat", 400)
            if absensi.jam_pulang is not None:
                return error("Tidak dapat memulai istirahat setelah check-out", 400)

            existing_break = (
                s.query(Istirahat)
                .filter(Istirahat.id_absensi == absensi.id_absensi, Istirahat.end_istirahat.is_(None))
                .first()
            )
            if existing_break:
                return error("Anda sudah dalam sesi istirahat", 409)

            now_local_dt = now_local()
            now_dt = now_local_dt.replace(tzinfo=None)

            jadwal_kerja = (
                s.query(ShiftKerja)
                .join(PolaKerja)
                .filter(
                    ShiftKerja.id_user == user_id,
                    ShiftKerja.tanggal_mulai <= today,
                    ShiftKerja.tanggal_selesai >= today,
                )
                .first()
            )

            if jadwal_kerja and jadwal_kerja.polaKerja:
                pola = jadwal_kerja.polaKerja
                if pola.jam_istirahat_mulai and pola.jam_istirahat_selesai:
                    jam_mulai_seharusnya = pola.jam_istirahat_mulai.time()
                    jam_selesai_seharusnya = pola.jam_istirahat_selesai.time()
                    jam_sekarang = now_local_dt.time()

                    if not (jam_mulai_seharusnya <= jam_sekarang <= jam_selesai_seharusnya):
                        return error(
                            f"Waktu istirahat hanya diizinkan antara {jam_mulai_seharusnya.strftime('%H:%M')} dan {jam_selesai_seharusnya.strftime('%H:%M')}",
                            403,
                        )

            new_break = Istirahat(
                id_user=user_id,
                id_absensi=absensi.id_absensi,
                tanggal_istirahat=today,
                start_istirahat=now_dt,
                start_istirahat_latitude=lat,
                start_istirahat_longitude=lng,
            )
            s.add(new_break)
            s.commit()
            s.refresh(new_break)

            return ok(
                message="Sesi istirahat dimulai",
                id_istirahat=new_break.id_istirahat,
                start_istirahat=new_break.start_istirahat.isoformat(),
            )

        except Exception as e:
            s.rollback()
            return error(f"Terjadi kesalahan: {str(e)}", 500)


@absensi_bp.post("/istirahat/end")
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
            absensi = (
                s.query(Absensi)
                .filter(Absensi.id_user == user_id, Absensi.tanggal == today)
                .one_or_none()
            )

            if absensi is None:
                return error("Absensi hari ini tidak ditemukan", 404)

            current_break = (
                s.query(Istirahat)
                .filter(Istirahat.id_absensi == absensi.id_absensi, Istirahat.end_istirahat.is_(None))
                .one_or_none()
            )

            if current_break is None:
                return error("Tidak ada sesi istirahat yang sedang berjalan", 404)

            now_dt = now_local().replace(tzinfo=None)
            current_break.end_istirahat = now_dt
            current_break.end_istirahat_latitude = lat
            current_break.end_istirahat_longitude = lng

            s.commit()

            return ok(
                message="Sesi istirahat selesai",
                id_istirahat=current_break.id_istirahat,
                end_istirahat=now_dt.isoformat(),
            )

        except Exception as e:
            s.rollback()
            return error(f"Terjadi kesalahan: {str(e)}", 500)


@absensi_bp.get("/istirahat/status")
def istirahat_status():
    user_id = (request.args.get("user_id") or "").strip()
    if not user_id:
        return error("user_id wajib ada", 400)

    with get_session() as s:
        today = today_local_date()

        def serialize_istirahat(b: Istirahat):
            data = {
                "id_istirahat": b.id_istirahat,
                "tanggal_istirahat": b.tanggal_istirahat.isoformat(),
                "start_istirahat": b.start_istirahat.isoformat(),
                "start_istirahat_latitude": float(b.start_istirahat_latitude) if b.start_istirahat_latitude is not None else None,
                "start_istirahat_longitude": float(b.start_istirahat_longitude) if b.start_istirahat_longitude is not None else None,
                "end_istirahat": None,
                "end_istirahat_latitude": None,
                "end_istirahat_longitude": None,
                "duration_seconds": None,
            }
            if b.end_istirahat:
                data["end_istirahat"] = b.end_istirahat.isoformat()
                data["end_istirahat_latitude"] = float(b.end_istirahat_latitude) if b.end_istirahat_latitude is not None else None
                data["end_istirahat_longitude"] = float(b.end_istirahat_longitude) if b.end_istirahat_longitude is not None else None
                data["duration_seconds"] = int((b.end_istirahat - b.start_istirahat).total_seconds())
            return data

        all_breaks_today = (
            s.query(Istirahat)
            .join(Absensi)
            .filter(Absensi.id_user == user_id, Istirahat.tanggal_istirahat == today)
            .order_by(Istirahat.start_istirahat.asc())
            .all()
        )

        active_break = None
        history = []
        total_duration = 0

        for b in all_breaks_today:
            serialized = serialize_istirahat(b)
            history.append(serialized)
            if b.end_istirahat is None:
                active_break = serialized
            else:
                total_duration += serialized["duration_seconds"]

        status = "active" if active_break else "inactive"

        return ok(
            status=status,
            active_break=active_break,
            history=history,
            total_duration_seconds=total_duration,
        )
