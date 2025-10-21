# app/blueprints/location/routes.py
from __future__ import annotations

from flask import Blueprint, request, current_app
from ...utils.responses import ok, error
from ...utils.geo import haversine_m
from ...db import get_session
from ...db.models import Location, User

# Penting: JANGAN menaruh prefix "/api/location" di sini.
# Prefix akan dipasang saat register_blueprint() di create_app():
# app.register_blueprint(location_bp, url_prefix="/api/location")
location_bp = Blueprint("location", __name__)


def _serialize(loc: Location):
    return {
        "id_location": loc.id_location,
        "nama_kantor": loc.nama_kantor,
        "latitude": float(loc.latitude),
        "longitude": float(loc.longitude),
        "radius": int(loc.radius) if loc.radius is not None else None,
    }


@location_bp.get("/")
def list_locations():
    """List + search + pagination: GET /api/location?q=&page=&page_size="""
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", type=int, default=1)
    page_size = request.args.get("page_size", type=int, default=20)
    page = 1 if not page or page < 1 else page
    page_size = 20 if not page_size or page_size < 1 else min(page_size, 100)

    with get_session() as s:
        qry = s.query(Location).filter(Location.deleted_at.is_(None))
        if q:
            like = f"%{q}%"
            # ILIKE untuk PostgreSQL; untuk MySQL bisa diakali dengan lower()
            qry = qry.filter(Location.nama_kantor.ilike(like))
        total = qry.count()
        items = (
            qry.order_by(Location.nama_kantor.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return ok(total=total, page=page, page_size=page_size, items=[_serialize(l) for l in items])


@location_bp.get("/<loc_id>")
def get_location(loc_id: str):
    with get_session() as s:
        loc = s.get(Location, loc_id)
        if loc is None or loc.deleted_at is not None:
            return error("Lokasi tidak ditemukan", 404)
        return ok(**_serialize(loc))


@location_bp.get("/nearest")
def nearest_location():
    """Lokasi terdekat: GET /api/location/nearest?lat=&lng=&radius_m=&limit="""
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    radius_m = request.args.get("radius_m", type=float)  # optional filter
    limit = request.args.get("limit", type=int, default=1)
    limit = 1 if not limit or limit < 1 else min(limit, 10)
    if lat is None or lng is None:
        return error("lat & lng wajib ada", 400)

    with get_session() as s:
        locs = s.query(Location).filter(Location.deleted_at.is_(None)).all()
        pairs = []
        for l in locs:
            d = haversine_m(lng, lat, float(l.longitude), float(l.latitude))
            pairs.append((l, d))
        pairs.sort(key=lambda x: x[1])
        if radius_m is not None:
            pairs = [p for p in pairs if p[1] <= float(radius_m)]
        picked = pairs[:limit]
        return ok(
            count=len(picked),
            items=[{**_serialize(l), "distanceMeters": float(d)} for l, d in picked],
        )


@location_bp.get("/my")
def my_location():
    """Kantor default user: GET /api/location/my?user_id="""
    user_id = (request.args.get("user_id") or "").strip()
    if not user_id:
        return error("user_id wajib ada", 400)
    with get_session() as s:
        u = s.get(User, user_id)
        if u is None or not u.id_location:
            return ok(item=None)
        loc = s.get(Location, u.id_location)
        if loc is None or loc.deleted_at is not None:
            return ok(item=None)
        return ok(item=_serialize(loc))
