# worker.py

import time
import numpy as np
from io import BytesIO

# Impor kredensial dari config.py
from config import SUPABASE_URL, SUPABASE_KEY
# Impor logger yang sudah dikonfigurasi
from logger_config import log

# Impor library Supabase (pastikan sudah di-install)
try:
    from supabase import create_client, Client
except ImportError:
    log.error("Library 'supabase' tidak ditemukan. Silakan install dengan 'pip install supabase'")
    # Set Client ke None agar tidak error saat inisialisasi
    Client = None

# Inisialisasi Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if Client else None

def proses_pendaftaran_wajah_background(device_id: str, image_bytes: bytes):
    """
    Fungsi ini berjalan di background untuk memproses wajah,
    membuat embedding, dan mengunggah hasilnya ke Supabase.
    """
    log.info(f"PROSES DIMULAI untuk device_id: {device_id}")

    if not supabase:
        log.error("Supabase client tidak terinisialisasi. Proses dihentikan.")
        return

    try:
        # ===== LANGKAH 1: Analisis Wajah & Buat Embedding =====
        log.info("Langkah 1: Memulai analisis wajah dan pembuatan embedding...")
        
        # --- GANTI BAGIAN INI DENGAN KODE INSIGHTFACE ANDA ---
        # Simulasi proses yang memakan waktu
        time.sleep(3) 
        # Simulasi hasil embedding dari insightface
        embedding = np.random.rand(512).astype(np.float32) 
        log.info("Langkah 1: SUKSES - Embedding berhasil dibuat.")
        # ----------------------------------------------------

        # ===== LANGKAH 2: Upload Gambar Asli ke Supabase Storage =====
        file_path_in_storage = f"wajah/{device_id}.jpg"
        log.info(f"Langkah 2: Mencoba upload gambar ke Supabase Storage di path: {file_path_in_storage}")

        # Menggunakan 'upsert=True' akan menimpa file jika sudah ada
        supabase.storage.from_("images").upload(
            path=file_path_in_storage,
            file=image_bytes,
            file_options={"content-type": "image/jpeg", "upsert": "true"}
        )
        log.info("Langkah 2: SUKSES - Gambar asli berhasil diunggah.")

        # ===== LANGKAH 3: Upload Embedding .npy ke Supabase Storage =====
        embedding_file_path = f"embeddings/{device_id}.npy"
        log.info(f"Langkah 3: Mencoba upload file embedding ke Supabase di path: {embedding_file_path}")

        # Ubah numpy array ke bytes untuk diunggah
        buffer = BytesIO()
        np.save(buffer, embedding)
        embedding_bytes = buffer.getvalue()

        supabase.storage.from_("embeddings").upload(
            path=embedding_file_path,
            file=embedding_bytes,
            file_options={"content-type": "application/octet-stream", "upsert": "true"}
        )
        log.info("Langkah 3: SUKSES - File embedding .npy berhasil diunggah.")

        # ===== LANGKAH 4: Kirim Notifikasi (jika perlu) =====
        log.info("Langkah 4: (Simulasi) Mengirim notifikasi ke Firebase...")
        time.sleep(1) # Simulasi panggil API Firebase
        log.info("Langkah 4: SUKSES - Notifikasi berhasil dikirim.")

    except Exception as e:
        # Tangkap semua jenis error dan catat ke log
        log.error(f"GAGAL - Terjadi error pada proses untuk device_id {device_id}")
        log.exception(e) # log.exception() akan mencatat full stack trace errornya

    finally:
        log.info(f"PROSES SELESAI untuk device_id: {device_id}")