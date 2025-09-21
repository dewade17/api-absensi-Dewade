# app/routers/face.py  (atau sesuai path-mu saat ini)

from flask import Blueprint, request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ...utils.responses import ok, error
from ...services.face_service import enroll_user, verify_user
from ...services.storage.supabase_storage import list_objects, signed_url
# NOTE: Hapus import _user_root karena tidak dipakai pada blueprint ini
# from ...services.face_service import _user_root
from ...db import get_session
from ...db.models import Device, User
from ...utils.timez import now_local

face_bp = Blueprint("face", __name__)

@face_bp.post("/api/face/enroll")
def enroll():
    user_id = (request.form.get("user_id") or "").strip()
    if not user_id:
        return error("user_id wajib ada", 400)

    files = request.files.getlist("images")
    if not files:
        return error("Kirim minimal satu file di field 'images'", 400)

    try:
        # 1) Proses enroll wajah lebih dulu (ini tidak tergantung Device)
        data = enroll_user(user_id, files)

        # 2) Ambil data perangkat dari form (opsional)
        device_label = request.form.get("device_label") or None
        platform = request.form.get("platform") or None
        os_version = request.form.get("os_version") or None
        app_version = request.form.get("app_version") or None
        device_identifier = request.form.get("device_identifier") or None

        # 3) Simpan/Update Device hanya jika ada satu pun field perangkat
        if any([device_label, platform, os_version, app_version, device_identifier]):
            with get_session() as s:
                # 3a) Pastikan user ada — mencegah FK error 1452
                user = s.execute(
                    select(User).where(User.id_user == user_id)
                ).scalar_one_or_none()
                if user is None:
                    # Jangan insert device; kirim info jelas ke client
                    return error(
                        f"User dengan id_user '{user_id}' tidak ditemukan. "
                        "Pastikan sudah registrasi/terbuat sebelum mendaftarkan device.",
                        404
                    )

                # 3b) Upsert berdasarkan (id_user, device_identifier) bila disediakan
                #     Kalau device_identifier kosong, kita tetap buat record baru
                #     (tapi idealnya client mengirim device_identifier yang stabil).
                device = None
                if device_identifier:
                    device = s.execute(
                        select(Device).where(
                            Device.id_user == user_id,
                            Device.device_identifier == device_identifier
                        )
                    ).scalar_one_or_none()

                now_naive_utc = now_local().replace(tzinfo=None)

                if device is None:
                    # INSERT baru
                    device = Device(
                        id_user=user_id,
                        device_label=device_label,
                        platform=platform,
                        os_version=os_version,
                        app_version=app_version,
                        device_identifier=device_identifier,
                        last_seen=now_naive_utc,
                    )
                    s.add(device)
                else:
                    # UPDATE existing
                    if device_label:
                        device.device_label = device_label
                    if platform:
                        device.platform = platform
                    if os_version:
                        device.os_version = os_version
                    if app_version:
                        device.app_version = app_version
                    device.last_seen = now_naive_utc

                try:
                    s.commit()
                except IntegrityError as ie:
                    s.rollback()
                    # Biasanya ini kena constraint lain; bungkus jadi pesan yang jelas
                    return error(f"Gagal menyimpan device (integrity error): {str(ie.orig)}", 400)

                # Pastikan objek sinkron
                s.refresh(device)
                # Tambahkan id_device ke respons
                data["device_id"] = device.id_device

        return ok(**data)

    except Exception as e:
        # Tangkap error dari proses enroll wajah atau yang lain
        return error(str(e), 400)


@face_bp.post("/api/face/verify")
def verify():
    user_id = (request.form.get("user_id") or "").strip()
    metric = (request.form.get("metric") or "cosine").lower()
    threshold = request.form.get("threshold", type=float, default=(0.45 if metric == "cosine" else 1.4))
    f = request.files.get("image")

    if not user_id:
        return error("user_id wajib ada", 400)
    if f is None:
        return error("Field 'image' wajib ada", 400)

    try:
        data = verify_user(user_id, f, metric=metric, threshold=threshold)
        return ok(**data)
    except FileNotFoundError as e:
        return error(str(e), 404)
    except Exception as e:
        return error(str(e), 400)


# -------- New Routes --------
#
# Menyediakan GET endpoint untuk mengambil daftar objek face user dari Supabase Storage,
# termasuk signed URL agar bisa diunduh oleh client.

@face_bp.get("/api/face/<user_id>")
def get_face_data(user_id: str):
    """Retrieve face data objects for a given user from Supabase storage.

    Endpoint ini akan menampilkan semua objek (baseline images & embedding)
    di bawah folder pengguna: face_detection/<id_user>. Parameter ``user_id``
    adalah ID yang dipakai saat proses enroll.
    Bila pengguna belum punya data wajah, akan mengembalikan items=[].
    """
    user_id = (user_id or "").strip()
    if not user_id:
        return error("user_id wajib ada", 400)

    try:
        prefix = f"face_detection/{user_id}"

        items = list_objects(prefix)
        files = []
        for item in items:
            name = item.get("name") or item.get("Name")
            if not name:
                continue

            path = f"{prefix}/{name}"
            url = signed_url(path)
            files.append({
                "name": name,
                "path": path,
                "signed_url": url
            })

        return ok(user_id=user_id, prefix=prefix, count=len(files), items=files)
    except Exception as e:
        return error(str(e), 400)
