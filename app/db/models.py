# app/db/models.py
from enum import Enum as PyEnum
import uuid
from sqlalchemy import (
    CHAR, Column, String, DateTime, Date, Enum, Integer, Text, ForeignKey,
    Boolean, UniqueConstraint, Index, DECIMAL, func
)
from sqlalchemy.orm import relationship
from . import Base

# ===== Enums (Diperbarui) =====

class Role(PyEnum):
    KARYAWAN = "KARYAWAN"
    HR = "HR"
    OPERASIONAL = "OPERASIONAL"
    DIREKTUR = "DIREKTUR"
    SUPERADMIN = "SUPERADMIN"
    SUBADMIN = "SUBADMIN"
    SUPERVISI = "SUPERVISI"


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
    menunggu = "menunggu"


class WorkStatus(PyEnum):
    berjalan = "berjalan"
    berhenti = "berhenti"
    selesai = "selesai"

# BARU
class StatusKerja(PyEnum):
    AKTIF = "AKTIF"
    TIDAK_AKTIF = "TIDAK_AKTIF"
    CUTI = "CUTI"

# BARU
class JenisKelamin(PyEnum):
    LAKI_LAKI = "LAKI_LAKI"
    PEREMPUAN = "PEREMPUAN"

# BARU
class Impact(PyEnum):
    PERSONAL = "PERSONAL"
    COMPANY = "COMPANY"
    

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


class ReportStatus(PyEnum):
    terkirim = "terkirim"
    disetujui = "disetujui"
    ditolak = "ditolak"


class AgendaStatus(PyEnum):
    diproses = "diproses"
    ditunda = "ditunda"
    selesai = "selesai"

# BARU
class StatusKunjungan(PyEnum):
    diproses = "diproses"
    berlangsung = "berlangsung"
    selesai = "selesai"


class NotificationStatus(PyEnum):
    unread = "unread"
    read = "read"
    archived = "archived"


# ===== Models =====

class Location(Base):
    __tablename__ = "location"
    id_location = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
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
    id_broadcasts = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(Text, nullable=False)
    message = Column(Text, nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    recipients = relationship("BroadcastRecipient", back_populates="broadcast", cascade="all, delete-orphan")


class BroadcastRecipient(Base):
    __tablename__ = "broadcasts_recipients"
    id_broadcast_recipients = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_broadcast = Column(CHAR(36), ForeignKey("broadcasts.id_broadcasts", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    nama_karyawan_snapshot = Column(String(255), nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    broadcast = relationship("Broadcast", back_populates="recipients")
    user = relationship("User", back_populates="broadcast_rcv")

    __table_args__ = (
        Index("idx_br_id_broadcast", "id_broadcast"),
        Index("idx_br_id_user", "id_user"),
    )


class Cuti(Base):
    __tablename__ = "Cuti"
    id_cuti = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    tanggal_pengajuan = Column(Date)
    tanggal_mulai = Column(Date)
    tanggal_selesai = Column(Date)
    bukti_url = Column(Text)
    keterangan = Column(Enum(CutiType), nullable=False)
    alasan = Column(Text)
    status = Column(Enum(ApproveStatus), nullable=False)
    current_level = Column(Integer)
    
    # ----- PENAMBAHAN DARI PRISMA -----
    impact = Column(Enum(Impact))
    hand_over = Column(Text)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    user = relationship("User", back_populates="cuti")
    approvals = relationship("CutiApproval", back_populates="cuti", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_cuti_id_user", "id_user"),)


class CutiApproval(Base):
    __tablename__ = "cuti_approval"
    id_cuti_approval = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_cuti = Column(CHAR(36), ForeignKey("Cuti.id_cuti", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    level = Column(Integer, nullable=False)
    approver_user_id = Column(CHAR(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"))
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
        Index("idx_ca_id_cuti_level", "id_cuti", "level"),
        Index("idx_ca_approver_user_id", "approver_user_id"),
    )

# ----- BARU: Ditambahkan dari prisma -----
class CutiKonfigurasi(Base):
    __tablename__ = "cuti_konfigurasi"
    id_cuti_konfigurasi = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bulan = Column(Enum(Bulan), nullable=False)
    kouta_cuti = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)


class PolaKerja(Base):
    __tablename__ = "pola_kerja"
    id_pola_kerja = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nama_pola_kerja = Column(String(255), nullable=False)
    jam_mulai = Column(DateTime, nullable=False)
    jam_selesai = Column(DateTime, nullable=False)
    jam_istirahat_mulai = Column(DateTime)
    jam_istirahat_selesai = Column(DateTime)
    maks_jam_istirahat = Column(Integer)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    shifts = relationship("ShiftKerja", back_populates="polaKerja")


class ShiftKerja(Base):
    __tablename__ = "shift_kerja"
    id_shift_kerja = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    tanggal_mulai = Column(Date)
    tanggal_selesai = Column(Date)
    hari_kerja = Column(String, nullable=False)
    status = Column(Enum(ShiftStatus), nullable=False)
    id_pola_kerja = Column(CHAR(36), ForeignKey("pola_kerja.id_pola_kerja", ondelete="RESTRICT", onupdate="CASCADE"))

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    user = relationship("User", back_populates="shifts")
    polaKerja = relationship("PolaKerja", back_populates="shifts")

    __table_args__ = (
        Index("idx_sk_id_user_tanggal_mulai", "id_user", "tanggal_mulai"),
        Index("idx_sk_id_pola_kerja", "id_pola_kerja"),
    )


class Agenda(Base):
    __tablename__ = "agenda"
    id_agenda = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nama_agenda = Column(Text, nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    items = relationship("AgendaKerja", back_populates="agenda")


class AgendaKerja(Base):
    __tablename__ = "agenda_kerja"
    id_agenda_kerja = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_absensi = Column(CHAR(36), ForeignKey("Absensi.id_absensi", ondelete="SET NULL", onupdate="CASCADE"))
    id_agenda = Column(CHAR(36), ForeignKey("agenda.id_agenda", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    deskripsi_kerja = Column(Text, nullable=False)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    duration_seconds = Column(Integer)
    status = Column(Enum(AgendaStatus), nullable=False)
    kebutuhan_agenda = Column(String(255)) # BARU

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    user = relationship("User", back_populates="agendas")
    absensi = relationship("Absensi", back_populates="agendas")
    agenda = relationship("Agenda", back_populates="items")

    __table_args__ = (
        Index("idx_ak_id_user_start_date", "id_user", "start_date"),
        Index("idx_ak_id_absensi", "id_absensi"),
        Index("idx_ak_id_agenda", "id_agenda"),
    )

# BARU
class KategoriKunjungan(Base):
    __tablename__ = "kategori_kunjungan"
    id_kategori_kunjungan = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kategori_kunjungan = Column(String(191), unique=True, nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)
    
    kunjungan = relationship("Kunjungan", back_populates="kategori")

# DIPERBARUI
class Kunjungan(Base):
    __tablename__ = "kunjungan"
    id_kunjungan = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    id_kategori_kunjungan = Column(CHAR(36), ForeignKey("kategori_kunjungan.id_kategori_kunjungan", ondelete="SET NULL", onupdate="CASCADE"))
    tanggal = Column(Date)
    jam_mulai = Column(DateTime)
    jam_selesai = Column(DateTime)
    deskripsi = Column(Text)
    jam_checkin = Column(DateTime)
    jam_checkout = Column(DateTime)
    start_latitude = Column(DECIMAL(10, 6))
    start_longitude = Column(DECIMAL(10, 6))
    end_latitude = Column(DECIMAL(10, 6))
    end_longitude = Column(DECIMAL(10, 6))
    lampiran_kunjungan_url = Column(Text)
    status_kunjungan = Column(Enum(StatusKunjungan), nullable=False, default=StatusKunjungan.diproses)
    duration = Column(Integer)
    hand_over = Column(Text)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    user = relationship("User", back_populates="kunjungan")
    kategori = relationship("KategoriKunjungan", back_populates="kunjungan")
    reports = relationship("KunjunganReportRecipient", back_populates="kunjungan", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_k_id_user_tanggal", "id_user", "tanggal"),
        Index("idx_k_id_kategori_kunjungan", "id_kategori_kunjungan"),
    )


class KunjunganReportRecipient(Base):
    __tablename__ = "kunjungan_report_recipients"
    id_kunjungan_report_recipient = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_kunjungan = Column(CHAR(36), ForeignKey("kunjungan.id_kunjungan", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    recipient_nama_snapshot = Column(String(255), nullable=False) # BARU
    recipient_role_snapshot = Column(Enum(AtasanRole))
    catatan = Column(Text)
    status = Column(Enum(ReportStatus), nullable=False, default=ReportStatus.terkirim)
    notified_at = Column(DateTime)
    read_at = Column(DateTime)
    acted_at = Column(DateTime)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    kunjungan = relationship("Kunjungan", back_populates="reports")
    recipient = relationship("User", back_populates="kunjungan_reports_received")

    __table_args__ = (
        UniqueConstraint("id_kunjungan", "id_user", name="uq_krr_kunjungan_user"),
        Index("idx_krr_id_kunjungan", "id_kunjungan"),
        Index("idx_krr_id_user", "id_user"),
    )


class User(Base):
    __tablename__ = "user"
    id_user = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nama_pengguna = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    kontak = Column(String(32))
    kontak_darurat = Column(String(32))
    password_updated_at = Column(DateTime)
    agama = Column(String(32))
    foto_profil_user = Column(Text)
    tanggal_lahir = Column(Date)
    role = Column(Enum(Role), nullable=False)
    id_departement = Column(CHAR(36), ForeignKey("departement.id_departement", ondelete="SET NULL", onupdate="CASCADE"))
    id_location = Column(CHAR(36), ForeignKey("location.id_location", ondelete="RESTRICT", onupdate="CASCADE"))
    reset_password_token = Column(String(255))
    reset_password_expires_at = Column(DateTime)
    tempat_lahir = Column(String(255))
    jenis_kelamin = Column(Enum(JenisKelamin))
    golongan_darah = Column(String(5))
    status_perkawinan = Column(String(50))
    alamat_ktp = Column(Text)
    alamat_ktp_provinsi = Column(String(255))
    alamat_ktp_kota = Column(String(255))
    alamat_domisili = Column(Text)
    alamat_domisili_provinsi = Column(String(255))
    alamat_domisili_kota = Column(String(255))
    zona_waktu = Column(String(50))
    jenjang_pendidikan = Column(String(50))
    jurusan = Column(String(100))
    nama_institusi_pendidikan = Column(String(255))
    tahun_lulus = Column(Integer)
    nomor_induk_karyawan = Column(String(100), unique=True)
    divisi = Column(String(100))
    id_jabatan = Column(CHAR(36), ForeignKey("jabatan.id_jabatan", ondelete="SET NULL", onupdate="CASCADE"))
    status_kerja = Column(Enum(StatusKerja))
    tanggal_mulai_bekerja = Column(Date)
    nomor_rekening = Column(String(50))
    jenis_bank = Column(String(50))

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    departement = relationship("Departement", back_populates="users", foreign_keys=[id_departement])
    kantor = relationship("Location", back_populates="users")
    jabatan = relationship("Jabatan", back_populates="users")

    faces = relationship("Face", back_populates="user", cascade="all, delete-orphan")
    agendas = relationship("AgendaKerja", back_populates="user", foreign_keys="AgendaKerja.id_user")
    cuti = relationship("Cuti", back_populates="user", foreign_keys="Cuti.id_user")
    shifts = relationship("ShiftKerja", back_populates="user", foreign_keys="ShiftKerja.id_user")
    story_planners = relationship("StoryPlanner", back_populates="user", foreign_keys="StoryPlanner.id_user")
    absensi = relationship("Absensi", back_populates="user", foreign_keys="Absensi.id_user")
    lembur = relationship("Lembur", back_populates="user", foreign_keys="Lembur.id_user")
    shift_piket = relationship("ShiftPiket", back_populates="user", foreign_keys="ShiftPiket.id_user")
    shift_storyPlanner = relationship("ShiftStoryPlanner", back_populates="user", foreign_keys="ShiftStoryPlanner.id_user")
    broadcast_rcv = relationship("BroadcastRecipient", back_populates="user", foreign_keys="BroadcastRecipient.id_user")
    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    cuti_approvals = relationship("CutiApproval", back_populates="approver", foreign_keys="CutiApproval.approver_user_id")
    lembur_approvals = relationship("LemburApproval", back_populates="approver", foreign_keys="LemburApproval.approver_user_id")
    absensi_reports_received = relationship("AbsensiReportRecipient", back_populates="recipient", foreign_keys="AbsensiReportRecipient.id_user")
    kunjungan = relationship("Kunjungan", back_populates="user", foreign_keys="Kunjungan.id_user")
    kunjungan_reports_received = relationship("KunjunganReportRecipient", back_populates="recipient", foreign_keys="KunjunganReportRecipient.id_user")
    notifications = relationship("Notification", back_populates="recipient", cascade="all, delete-orphan")
    istirahat = relationship("Istirahat", back_populates="user", cascade="all, delete-orphan")

    supervised_department = relationship("Departement", uselist=False, back_populates="supervisor", foreign_keys="Departement.id_supervisor")

    __table_args__ = (
        Index("idx_user_id_departement", "id_departement"),
        Index("idx_user_id_location", "id_location"),
        Index("idx_user_id_jabatan", "id_jabatan"),
    )


class Departement(Base):
    __tablename__ = "departement"
    id_departement = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nama_departement = Column(String(256), nullable=False)
    id_supervisor = Column(CHAR(36), ForeignKey("user.id_user", ondelete="SET NULL", onupdate="CASCADE"), unique=True) # BARU

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    users = relationship("User", back_populates="departement", foreign_keys="[User.id_departement]")
    jabatan = relationship("Jabatan", back_populates="departement")
    supervisor = relationship("User", back_populates="supervised_department", foreign_keys=[id_supervisor])
    StoryPlanner = relationship("StoryPlanner", back_populates="departement")


# BARU
class Jabatan(Base):
    __tablename__ = "jabatan"
    id_jabatan = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nama_jabatan = Column(String(256), nullable=False)
    id_departement = Column(CHAR(36), ForeignKey("departement.id_departement", ondelete="SET NULL", onupdate="CASCADE"))
    id_induk_jabatan = Column(CHAR(36), ForeignKey("jabatan.id_jabatan", ondelete="SET NULL")) # NoAction in SQL -> default onupdate

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    departement = relationship("Departement", back_populates="jabatan")
    induk = relationship("Jabatan", remote_side=[id_jabatan], back_populates="bawahan")
    bawahan = relationship("Jabatan", back_populates="induk")
    users = relationship("User", back_populates="jabatan")

    __table_args__ = (
        Index("idx_j_id_departement", "id_departement"),
        Index("idx_j_id_induk_jabatan", "id_induk_jabatan"),
    )

# BARU
class Istirahat(Base):
    __tablename__ = "istirahat"
    id_istirahat = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    id_absensi = Column(CHAR(36), ForeignKey("Absensi.id_absensi", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    tanggal_istirahat = Column(Date, nullable=False)
    start_istirahat = Column(DateTime, nullable=False)
    end_istirahat = Column(DateTime)
    start_istirahat_latitude = Column(DECIMAL(10, 6))
    start_istirahat_longitude = Column(DECIMAL(10, 6))
    end_istirahat_latitude = Column(DECIMAL(10, 6))
    end_istirahat_longitude = Column(DECIMAL(10, 6))

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    user = relationship("User", back_populates="istirahat")
    absensi = relationship("Absensi", back_populates="istirahat")

    __table_args__ = (
        Index("idx_i_id_user_tanggal_istirahat", "id_user", "tanggal_istirahat"),
        Index("idx_i_id_absensi", "id_absensi"),
    )


class Face(Base):
    __tablename__ = "face"
    id_face = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    image_face = Column(Text, nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    user = relationship("User", back_populates="faces")

    __table_args__ = (Index("idx_f_id_user", "id_user"),)


class StoryPlanner(Base):
    __tablename__ = "story_planner"
    id_story = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    id_departement = Column(CHAR(36), ForeignKey("departement.id_departement", ondelete="SET NULL", onupdate="CASCADE"))
    deskripsi_kerja = Column(Text, nullable=False)
    count_time = Column(DateTime)
    status = Column(Enum(WorkStatus), nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    user = relationship("User", back_populates="story_planners")
    departement = relationship("Departement", back_populates="StoryPlanner")

    __table_args__ = (
        Index("idx_sp_id_user", "id_user"),
        Index("idx_sp_id_departement", "id_departement"),
    )


class Device(Base):
    __tablename__ = "device"
    id_device = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    device_label = Column(String(255))
    platform = Column(String(50))
    os_version = Column(String(50))
    app_version = Column(String(50))
    device_identifier = Column(String(191))
    last_seen = Column(DateTime)
    # ----- PENAMBAHAN DARI PRISMA -----
    fcm_token = Column(String(1024))
    fcm_token_updated_at = Column(DateTime)
    push_enabled = Column(Boolean, nullable=False, default=True)
    last_push_at = Column(DateTime)
    failed_push_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    user = relationship("User", back_populates="devices")

    __table_args__ = (
        Index("idx_d_id_user", "id_user"),
        Index("idx_d_device_identifier", "device_identifier"),
        Index("idx_d_fcm_token", "fcm_token", mysql_length=191),
    )


class Absensi(Base):
    __tablename__ = "Absensi"
    id_absensi = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    face_verified_masuk = Column(Boolean, nullable=False)
    face_verified_pulang = Column(Boolean, nullable=False)
    tanggal = Column(Date)
    id_lokasi_pulang = Column(CHAR(36), ForeignKey("location.id_location", ondelete="SET NULL", onupdate="CASCADE"))
    id_lokasi_datang = Column(CHAR(36), ForeignKey("location.id_location", ondelete="SET NULL", onupdate="CASCADE"))
    jam_masuk = Column(DateTime)
    jam_pulang = Column(DateTime)
    status_masuk = Column(Enum(AbsensiStatus))
    status_pulang = Column(Enum(AbsensiStatus))
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
    agendas = relationship("AgendaKerja", back_populates="absensi")
    report_recipients = relationship("AbsensiReportRecipient", back_populates="absensi", cascade="all, delete-orphan")
    catatan = relationship("Catatan", back_populates="absensi", cascade="all, delete-orphan")
    istirahat = relationship("Istirahat", back_populates="absensi", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("id_user", "tanggal", name="uq_absensi_user_tanggal"),
        Index("idx_abs_id_user_tanggal", "id_user", "tanggal"),
        Index("idx_abs_id_lokasi_datang", "id_lokasi_datang"),
        Index("idx_abs_id_lokasi_pulang", "id_lokasi_pulang"),
    )


class AbsensiReportRecipient(Base):
    __tablename__ = "absensi_report_recipients"
    id_absensi_report_recipient = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_absensi = Column(CHAR(36), ForeignKey("Absensi.id_absensi", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    recipient_nama_snapshot = Column(String(255), nullable=False) # BARU
    recipient_role_snapshot = Column(Enum(AtasanRole))
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
        UniqueConstraint("id_absensi", "id_user", name="uq_arr_absensi_user"),
        Index("idx_arr_id_absensi", "id_absensi"),
        Index("idx_arr_id_user", "id_user"),
    )


class Catatan(Base):
    __tablename__ = "catatan"
    id_catatan = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_absensi = Column(CHAR(36), ForeignKey("Absensi.id_absensi", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    deskripsi_catatan = Column(Text, nullable=False)
    lampiran_url = Column(Text)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    absensi = relationship("Absensi", back_populates="catatan")

    __table_args__ = (
        Index("idx_c_id_absensi", "id_absensi"),
    )


class Notification(Base):
    __tablename__ = "notifications"
    id_notification = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    data_json = Column(Text)
    related_table = Column(String(64))
    related_id = Column(CHAR(36))
    status = Column(Enum(NotificationStatus), nullable=False, default=NotificationStatus.unread)
    seen_at = Column(DateTime)
    read_at = Column(DateTime)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    recipient = relationship("User", back_populates="notifications")

    __table_args__ = (
        Index("idx_n_id_user_status_created_at", "id_user", "status", "created_at"),
        Index("idx_n_related_table_related_id", "related_table", "related_id"),
    )


# BARU: Template Notifikasi
#
# Model ini menyimpan template notifikasi yang dapat dikonfigurasi oleh
# administrator. Mirip dengan model `notification_templates` di backend
# Next.js, ia menyimpan kode pemicu (`event_trigger`), deskripsi singkat
# untuk HR, template judul, template isi, daftar placeholder yang dapat
# digunakan dalam template, dan status aktif. Template default dapat diisi
# melalui skrip seeding. Service notifikasi akan mengambil baris ini
# berdasarkan `event_trigger` dan mengganti placeholder dengan data dinamis.
class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Kode unik yang digunakan untuk memicu template, misal: "REMINDER_CHECK_IN"
    event_trigger = Column(String(64), unique=True, nullable=False)
    # Deskripsi internal untuk HR/admin
    description = Column(String(255), nullable=False)
    # Template judul pesan; placeholder dibungkus dengan {..}
    title_template = Column(String(255), nullable=False)
    # Template isi pesan; placeholder dibungkus dengan {..}
    body_template = Column(Text, nullable=False)
    # Daftar placeholder yang tersedia, disimpan dalam satu string (opsional)
    placeholders = Column(String(255))
    # Menandakan apakah template aktif. Jika false, template tidak digunakan.
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Lembur(Base):
    __tablename__ = "Lembur"
    id_lembur = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
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
    approvals = relationship("LemburApproval", back_populates="lembur", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_l_id_user_tanggal", "id_user", "tanggal"),
        Index("idx_l_status", "status"),
    )


class LemburApproval(Base):
    __tablename__ = "lembur_approval"
    id_lembur_approval = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_lembur = Column(CHAR(36), ForeignKey("Lembur.id_lembur", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    level = Column(Integer, nullable=False)
    approver_user_id = Column(CHAR(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"))
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
        Index("idx_la_id_lembur_level", "id_lembur", "level"),
        Index("idx_la_approver_user_id", "approver_user_id"),
    )


class JadwalPiket(Base):
    __tablename__ = "jadwal_piket"
    id_jadwal_piket = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    Tahun = Column(Date)
    Bulan = Column(Enum(Bulan), nullable=False)
    keterangan = Column(Text)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    shifts = relationship("ShiftPiket", back_populates="jadwal", cascade="all, delete-orphan")


class JadwalStoryPlanner(Base):
    __tablename__ = "jadwal_story_planer"
    id_jadwal_story_planner = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    Tahun = Column(Date)
    Bulan = Column(Enum(Bulan), nullable=False)
    keterangan = Column(Text)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    shifts = relationship("ShiftStoryPlanner", back_populates="jadwal", cascade="all, delete-orphan")


class ShiftPiket(Base):
    __tablename__ = "shift_piket"
    id_shift_piket = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_jadwal_piket = Column(CHAR(36), ForeignKey("jadwal_piket.id_jadwal_piket", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    hari_piket = Column(String, nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    jadwal = relationship("JadwalPiket", back_populates="shifts")
    user = relationship("User", back_populates="shift_piket")

    __table_args__ = (
        Index("idx_sp_id_jadwal_piket", "id_jadwal_piket"),
        Index("idx_sp_id_user", "id_user"),
    )


class ShiftStoryPlanner(Base):
    __tablename__ = "shift_story_planer"
    id_shift_story_planner = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_jadwal_story_planner = Column(CHAR(36), ForeignKey("jadwal_story_planer.id_jadwal_story_planner", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    id_user = Column(CHAR(36), ForeignKey("user.id_user", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    hari_story_planner = Column(String, nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime)

    jadwal = relationship("JadwalStoryPlanner", back_populates="shifts")
    user = relationship("User", back_populates="shift_storyPlanner")

    __table_args__ = (
        Index("idx_ssp_id_jadwal_story_planner", "id_jadwal_story_planner"),
        Index("idx_ssp_id_user", "id_user"),
    )