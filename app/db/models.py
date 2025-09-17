# app/db/models.py
from enum import Enum as PyEnum
import uuid
from sqlalchemy import (
    CHAR, Column, String, DateTime, Date, Enum, Integer, Text, ForeignKey,
    Boolean, UniqueConstraint, Index, DECIMAL, func
)
from sqlalchemy.orm import relationship
from . import Base

# ===== Enums =====

class Role(PyEnum):
    KARYAWAN = "KARYAWAN"
    HR = "HR"
    OPERASIONAL = "OPERASIONAL"
    DIREKTUR = "DIREKTUR"

# Role atasan (tanpa KARYAWAN) untuk persetujuan/approval
class AtasanRole(PyEnum):
    HR = "HR"
    OPERASIONAL = "OPERASIONAL"
    DIREKTUR = "DIREKTUR"

class CutiType(PyEnum):
    cuti = "cuti"
    sakit = "sakit"
    izin = "izin"

class ApproveStatus(PyEnum):
    disetujui = "disetujui"
    ditolak = "ditolak"
    pending = "pending"

class WorkStatus(PyEnum):
    berjalan = "berjalan"
    berhenti = "berhenti"
    selesai = "selesai"

class ShiftStatus(PyEnum):
    KERJA = "KERJA"
    LIBUR = "LIBUR"

class AbsensiStatus(PyEnum):
    tepat = "tepat"
    terlambat = "terlambat"

class LemburStatus(PyEnum):
    pending = "pending"
    disetujui = "disetujui"
    ditolak = "ditolak"

class Bulan(PyEnum):
    JANUARI = "JANUARI"
    FEBRUARI = "FEBRUARI"
    MARET = "MARET"
    APRIL = "APRIL"
    MEI = "MEI"
    JUNI = "JUNI"
    JULI = "JULI"
    AGUSTUS = "AGUSTUS"
    SEPTEMBER = "SEPTEMBER"
    OKTOBER = "OKTOBER"
    NOVEMBER = "NOVEMBER"
    DESEMBER = "DESEMBER"

# Hanya status valid untuk persetujuan laporan absensi
class ReportStatus(PyEnum):
    terkirim = "terkirim"
    disetujui = "disetujui"
    ditolak = "ditolak"

# Status khusus Agenda Kerja
class AgendaStatus(PyEnum):
    diproses = "diproses"
    ditunda = "ditunda"
    selesai = "selesai"


# ===== Models =====

class Location(Base):
    __tablename__ = "location"
    id_location = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nama_kantor = Column(String(255), nullable=False)
    latitude = Column(DECIMAL(10, 6), nullable=False)
    longitude = Column(DECIMAL(10, 6), nullable=False)
    radius = Column(Integer)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    absensi_datang = relationship("Absensi", back_populates="lokasiIn", foreign_keys="Absensi.id_lokasi_datang")
    absensi_pulang = relationship("Absensi", back_populates="lokasiOut", foreign_keys="Absensi.id_lokasi_pulang")
    users = relationship("User", back_populates="kantor")


class Broadcast(Base):
    __tablename__ = "broadcasts"
    id_broadcasts = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(Text, nullable=False)
    message = Column(Text, nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    recipients = relationship("BroadcastRecipient", back_populates="broadcast")


class BroadcastRecipient(Base):
    __tablename__ = "broadcasts_recipients"
    id_broadcast_recipients = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_broadcast = Column(String(36), ForeignKey("broadcasts.id_broadcasts", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    id_user = Column(String(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    nama_karyawan_snapshot = Column(String(255), nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    broadcast = relationship("Broadcast", back_populates="recipients")
    user = relationship("User", back_populates="broadcast_rcv")

    __table_args__ = (
        Index("idx_brc_id_broadcast", "id_broadcast"),
        Index("idx_brc_id_user", "id_user"),
    )


class Cuti(Base):
    __tablename__ = "Cuti"
    id_cuti = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(String(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    tanggal_pengajuan = Column(Date)
    tanggal_mulai = Column(Date)
    tanggal_selesai = Column(Date)
    bukti_url = Column(Text)
    keterangan = Column(Enum(CutiType), nullable=False)
    alasan = Column(Text)
    status = Column(Enum(ApproveStatus), nullable=False)
    current_level = Column(Integer)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    user = relationship("User", back_populates="cuti")
    approvals = relationship("CutiApproval", back_populates="cuti")

    __table_args__ = (Index("idx_cuti_user", "id_user"),)


class CutiApproval(Base):
    __tablename__ = "cuti_approval"
    id_cuti_approval = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_cuti = Column(String(36), ForeignKey("Cuti.id_cuti", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    level = Column(Integer, nullable=False)
    approver_user_id = Column(String(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"))
    approver_role = Column(Enum(Role))
    decision = Column(Enum(ApproveStatus), nullable=False, default=ApproveStatus.pending)
    decided_at = Column(DateTime)
    note = Column(Text)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    cuti = relationship("Cuti", back_populates="approvals")
    approver = relationship("User", back_populates="cuti_approvals", foreign_keys=[approver_user_id])

    __table_args__ = (
        Index("idx_cuti_level", "id_cuti", "level"),
        Index("idx_cuti_approver", "approver_user_id"),
    )


class PolaKerja(Base):
    __tablename__ = "pola_kerja"
    id_pola_kerja = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nama_pola_kerja = Column(String(255), nullable=False)
    jam_mulai = Column(DateTime, nullable=False)
    jam_selesai = Column(DateTime, nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    shifts = relationship("ShiftKerja", back_populates="polaKerja")


class ShiftKerja(Base):
    __tablename__ = "shift_kerja"
    id_shift_kerja = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(String(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    tanggal_mulai = Column(Date)
    tanggal_selesai = Column(Date)
    # MySQL SET('senin','selasa','rabu','kamis','jumat','sabtu','minggu') disimpan sebagai string
    hari_kerja = Column(String, nullable=False)
    status = Column(Enum(ShiftStatus), nullable=False)
    id_pola_kerja = Column(String(36), ForeignKey("pola_kerja.id_pola_kerja", ondelete="RESTRICT", onupdate="CASCADE"))

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    user = relationship("User", back_populates="shifts")
    polaKerja = relationship("PolaKerja", back_populates="shifts")

    __table_args__ = (
        Index("idx_shift_user_start", "id_user", "tanggal_mulai"),
        Index("idx_shift_pola", "id_pola_kerja"),
    )


# ===== AGENDA (Master) =====
class Agenda(Base):
    __tablename__ = "agenda"
    id_agenda = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nama_agenda = Column(Text, nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    # Detail items
    items = relationship("AgendaKerja", back_populates="agenda")


# ===== AGENDA_KERJA (Detail) =====
class AgendaKerja(Base):
    __tablename__ = "agenda_kerja"
    id_agenda_kerja = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_absensi = Column(String(36), ForeignKey("Absensi.id_absensi", ondelete="SET NULL", onupdate="CASCADE"))
    id_agenda = Column(String(36), ForeignKey("agenda.id_agenda", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    id_user = Column(String(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)

    deskripsi_kerja = Column(Text, nullable=False)
    start_date = Column(DateTime)    # nullable
    end_date = Column(DateTime)      # nullable
    duration_seconds = Column(Integer)

    status = Column(Enum(AgendaStatus), nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    # Relations
    user = relationship("User", back_populates="agendas")
    absensi = relationship("Absensi", back_populates="agendas")
    agenda = relationship("Agenda", back_populates="items")

    __table_args__ = (
        Index("idx_agker_user_start", "id_user", "start_date"),
        Index("idx_agker_absensi", "id_absensi"),
        Index("idx_agker_agenda", "id_agenda"),
    )


class Departement(Base):
    __tablename__ = "departement"
    id_departement = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nama_departement = Column(String(256), nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    users = relationship("User", back_populates="departement")
    story_planners = relationship("StoryPlanner", back_populates="departement")


class User(Base):
    __tablename__ = "user"
    id_user = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nama_pengguna = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    kontak = Column(String(32))
    password_updated_at = Column(DateTime)
    agama = Column(String(32))
    foto_profil_user = Column(Text)
    tanggal_lahir = Column(Date)
    role = Column(Enum(Role), nullable=False)
    id_departement = Column(String(36), ForeignKey("departement.id_departement", ondelete="SET NULL", onupdate="CASCADE"))
    id_location = Column(String(36), ForeignKey("location.id_location", ondelete="RESTRICT", onupdate="CASCADE"))
    reset_password_token = Column(String(255))
    reset_password_expires_at = Column(DateTime)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    departement = relationship("Departement", back_populates="users")
    kantor = relationship("Location", back_populates="users")

    faces = relationship("Face", back_populates="user")
    agendas = relationship("AgendaKerja", back_populates="user")  # tetap pakai nama field lama untuk kompatibilitas
    cuti = relationship("Cuti", back_populates="user")
    shifts = relationship("ShiftKerja", back_populates="user")
    story_planners = relationship("StoryPlanner", back_populates="user")
    absensi = relationship("Absensi", back_populates="user")
    lembur = relationship("Lembur", back_populates="user")
    shift_piket = relationship("ShiftPiket", back_populates="user")
    shift_storyPlanner = relationship("ShiftStoryPlanner", back_populates="user")
    broadcast_rcv = relationship("BroadcastRecipient", back_populates="user")
    devices = relationship("Device", back_populates="user")
    cuti_approvals = relationship("CutiApproval", back_populates="approver")
    lembur_approvals = relationship("LemburApproval", back_populates="approver")

    absensi_reports_received = relationship("AbsensiReportRecipient", back_populates="recipient")

    __table_args__ = (
        Index("idx_user_dept", "id_departement"),
        Index("idx_user_loc", "id_location"),
    )


class Face(Base):
    __tablename__ = "face"
    id_face = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(String(36), ForeignKey("user.id_user", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    image_face = Column(Text, nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    user = relationship("User", back_populates="faces")

    __table_args__ = (Index("idx_face_user", "id_user"),)


class StoryPlanner(Base):
    __tablename__ = "story_planner"
    id_story = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(String(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    id_departement = Column(String(36), ForeignKey("departement.id_departement", ondelete="SET NULL", onupdate="CASCADE"))
    deskripsi_kerja = Column(Text, nullable=False)
    count_time = Column(DateTime)
    status = Column(Enum(WorkStatus), nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    user = relationship("User", back_populates="story_planners")
    departement = relationship("Departement", back_populates="story_planners")

    __table_args__ = (
        Index("idx_story_user", "id_user"),
        Index("idx_story_dept", "id_departement"),
    )


class Device(Base):
    __tablename__ = "device"
    id_device = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(String(36), ForeignKey("user.id_user", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    device_label = Column(String(255))
    platform = Column(String(50))
    os_version = Column(String(50))
    app_version = Column(String(50))
    device_identifier = Column(String(191))
    last_seen = Column(DateTime)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    user = relationship("User", back_populates="devices")

    __table_args__ = (Index("idx_device_user", "id_user"),)


class Absensi(Base):
    __tablename__ = "Absensi"
    id_absensi = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(String(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    face_verified_masuk = Column(Boolean, nullable=False, default=False)
    face_verified_pulang = Column(Boolean, nullable=False, default=False)
    tanggal = Column(Date)
    id_lokasi_pulang = Column(String(36), ForeignKey("location.id_location", ondelete="SET NULL", onupdate="CASCADE"))
    id_lokasi_datang = Column(String(36), ForeignKey("location.id_location", ondelete="SET NULL", onupdate="CASCADE"))
    jam_masuk = Column(DateTime)
    jam_pulang = Column(DateTime)
    status = Column(Enum(AbsensiStatus), nullable=False)

    in_latitude = Column(DECIMAL(10, 6))
    in_longitude = Column(DECIMAL(10, 6))
    out_latitude = Column(DECIMAL(10, 6))
    out_longitude = Column(DECIMAL(10, 6))

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    user = relationship("User", back_populates="absensi")
    lokasiIn = relationship("Location", foreign_keys=[id_lokasi_datang], back_populates="absensi_datang")
    lokasiOut = relationship("Location", foreign_keys=[id_lokasi_pulang], back_populates="absensi_pulang")

    agendas = relationship("AgendaKerja", back_populates="absensi")  # detail agenda per absensi/hari
    report_recipients = relationship("AbsensiReportRecipient", back_populates="absensi")
    catatan = relationship("Catatan", back_populates="absensi")  # <- relasi ke tabel catatan

    __table_args__ = (
        UniqueConstraint("id_user", "tanggal", name="uq_absensi_user_tanggal"),
        Index("idx_absensi_user_tanggal", "id_user", "tanggal"),
        Index("idx_absensi_datang", "id_lokasi_datang"),
        Index("idx_absensi_pulang", "id_lokasi_pulang"),
    )


class Lembur(Base):
    __tablename__ = "Lembur"
    id_lembur = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(String(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    tanggal = Column(Date)
    jam_mulai = Column(DateTime)
    jam_selesai = Column(DateTime)
    alasan = Column(Text)
    status = Column(Enum(LemburStatus), nullable=False)
    current_level = Column(Integer)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    user = relationship("User", back_populates="lembur")
    approvals = relationship("LemburApproval", back_populates="lembur")

    __table_args__ = (
        Index("idx_lembur_user_tanggal", "id_user", "tanggal"),
        Index("idx_lembur_status", "status"),
    )


class LemburApproval(Base):
    __tablename__ = "lembur_approval"
    id_lembur_approval = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_lembur = Column(String(36), ForeignKey("Lembur.id_lembur", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    level = Column(Integer, nullable=False)
    approver_user_id = Column(String(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"))
    approver_role = Column(Enum(Role))
    decision = Column(Enum(ApproveStatus), nullable=False, default=ApproveStatus.pending)
    decided_at = Column(DateTime)
    note = Column(Text)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    lembur = relationship("Lembur", back_populates="approvals")
    approver = relationship("User", back_populates="lembur_approvals", foreign_keys=[approver_user_id])

    __table_args__ = (
        Index("idx_lembur_level", "id_lembur", "level"),
        Index("idx_lembur_approver", "approver_user_id"),
    )


class JadwalPiket(Base):
    __tablename__ = "jadwal_piket"
    id_jadwal_piket = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    Tahun = Column(Date)
    Bulan = Column(Enum(Bulan), nullable=False)
    keterangan = Column(Text)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    shifts = relationship("ShiftPiket", back_populates="jadwal")


class JadwalStoryPlanner(Base):
    __tablename__ = "jadwal_story_planer"
    id_jadwal_story_planner = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    Tahun = Column(Date)
    Bulan = Column(Enum(Bulan), nullable=False)
    keterangan = Column(Text)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    shifts = relationship("ShiftStoryPlanner", back_populates="jadwal")


class ShiftPiket(Base):
    __tablename__ = "shift_piket"
    id_shift_piket = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_jadwal_piket = Column(String(36), ForeignKey("jadwal_piket.id_jadwal_piket", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    id_user = Column(String(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    hari_piket = Column(String, nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    jadwal = relationship("JadwalPiket", back_populates="shifts")
    user = relationship("User", back_populates="shift_piket")

    __table_args__ = (
        Index("idx_shiftpiket_jadwal", "id_jadwal_piket"),
        Index("idx_shiftpiket_user", "id_user"),
    )


class ShiftStoryPlanner(Base):
    __tablename__ = "shift_story_planer"
    id_shift_story_planner = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_jadwal_story_planner = Column(String(36), ForeignKey("jadwal_story_planer.id_jadwal_story_planner", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    id_user = Column(String(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    hari_story_planner = Column(String, nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    jadwal = relationship("JadwalStoryPlanner", back_populates="shifts")
    user = relationship("User", back_populates="shift_storyPlanner")

    __table_args__ = (
        Index("idx_shiftsp_jadwal", "id_jadwal_story_planner"),
        Index("idx_shiftsp_user", "id_user"),
    )


# ===== Absensi Report Recipients =====
class AbsensiReportRecipient(Base):
    __tablename__ = "absensi_report_recipients"

    id_absensi_report_recipient = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_absensi = Column(String(36), ForeignKey("Absensi.id_absensi", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    id_user = Column(String(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)

    recipient_role_snapshot = Column(Enum(AtasanRole))  # snapshot hanya HR/OPERASIONAL/DIREKTUR
    catatan = Column(Text)
    status = Column(Enum(ReportStatus), nullable=False, default=ReportStatus.terkirim)
    notified_at = Column(DateTime)
    read_at = Column(DateTime)
    acted_at = Column(DateTime)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    absensi = relationship("Absensi", back_populates="report_recipients")
    recipient = relationship("User", back_populates="absensi_reports_received")

    __table_args__ = (
        Index("idx_arr_absensi", "id_absensi"),
        Index("idx_arr_user", "id_user"),
        UniqueConstraint("id_absensi", "id_user", name="uq_absensi_user_recipient"),
    )


# ===== Catatan Absensi =====
class Catatan(Base):
    __tablename__ = "catatan"

    id_catatan = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_absensi = Column(String(36), ForeignKey("Absensi.id_absensi", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    deskripsi_catatan = Column(Text, nullable=False)
    lampiran_url = Column(Text)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    absensi = relationship("Absensi", back_populates="catatan")

    __table_args__ = (
        Index("idx_catatan_absensi", "id_absensi"),
    )
