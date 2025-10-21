# app/db/attendance.py
from __future__ import annotations

"""
Adaptor kompatibilitas untuk kode lama yang mengimpor:
    from app.db.attendance import Base, Attendance

Di skema baru, modelnya bernama 'Absensi' di app/db/models.py.
File ini mengekspor ulang supaya impor lama tetap jalan.
"""

# Coba ambil Base dari lokasi yang tersedia di proyekmu
try:
    # Banyak proyek menaruh Base di models.py
    from .models import Base  # type: ignore
except Exception:
    try:
        # Alternatif umum: Base didefinisikan di package app.db.__init__
        from . import Base  # type: ignore
    except Exception:
        Base = None  # type: ignore

# Petakan 'Attendance' ke model 'Absensi'
from .models import Absensi as Attendance  # type: ignore

__all__ = ["Base", "Attendance"]
