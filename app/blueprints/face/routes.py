from flask import Blueprint, request
from ...utils.responses import ok, error
from ...services.face_service import enroll_user, verify_user
from ...services.storage.supabase_storage import list_objects, signed_url
from ...services.face_service import _user_root
from ...db import get_session
from ...db.models import Device
from ...utils.timez import now_local
from uuid import uuid4

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
        data = enroll_user(user_id, files)
        # Ambil data perangkat dari form jika disediakan
        device_label = request.form.get("device_label") or None
        platform = request.form.get("platform") or None
        os_version = request.form.get("os_version") or None
        app_version = request.form.get("app_version") or None
        device_identifier = request.form.get("device_identifier") or None
        # Simpan record Device hanya jika ada salah satu field perangkat
        if any([device_label, platform, os_version, app_version, device_identifier]):
            with get_session() as s:
                device = Device(
                    id_device=str(uuid4()),
                    id_user=user_id,
                    device_label=device_label,
                    platform=platform,
                    os_version=os_version,
                    app_version=app_version,
                    device_identifier=device_identifier,
                    last_seen=now_local().replace(tzinfo=None),
                )
                s.add(device)
                s.commit()
                # Tambahkan id_device ke respons
                data["device_id"] = device.id_device
        return ok(**data)
    except Exception as e:
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
# Provide a simple GET endpoint for retrieving face-related data for a
# particular user from Supabase storage.  When enrolling a user the
# application persists a number of baseline images and an embedding
# for each user under a path like ``face_detection/<slug|user_id>``.  This
# endpoint lists the stored objects for the user and returns signed
# download URLs for each object so that clients can fetch the images
# or embedding without requiring direct Supabase credentials.  If no
# objects exist for the given user the endpoint returns an empty list.

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
        # Langsung gunakan id_user sebagai nama folder
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
