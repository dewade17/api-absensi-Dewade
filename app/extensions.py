from typing import Optional
from flask import current_app
from flask_cors import CORS

from supabase import create_client, Client
from insightface.app import FaceAnalysis
import firebase_admin
from firebase_admin import credentials
import json
import os # <-- Tambahkan import 'os'

# Buat instance ekstensi di tingkat global
cors = CORS()

# Variabel global untuk klien/engine yang diinisialisasi sekali
_supabase: Optional[Client] = None
_engine: Optional[FaceAnalysis] = None
_firebase_app = None

def init_supabase(app):
    """Menginisialisasi dan menyimpan klien Supabase."""
    global _supabase
    url = app.config.get("SUPABASE_URL")
    key = app.config.get("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        _supabase = create_client(url, key)
    else:
        print("Peringatan: Kredensial Supabase tidak ditemukan.")

def get_supabase() -> Optional[Client]:
    return _supabase

def init_face_engine(app):
    """Menginisialisasi mesin pengenalan wajah."""
    global _engine
    model = app.config.get("MODEL_NAME", "buffalo_l")
    engine = FaceAnalysis(name=model, providers=["CPUExecutionProvider"])
    engine.prepare(ctx_id=0)
    _engine = engine
    print(f"Mesin pengenalan wajah diinisialisasi dengan model: {model}")

def get_face_engine() -> FaceAnalysis:
    if _engine is None:
        # Inisialisasi darurat jika belum diinisialisasi
        init_face_engine(current_app)
    return _engine

def init_firebase(app):
    """Menginisialisasi Firebase Admin SDK dengan logika yang lebih baik."""
    global _firebase_app
    if firebase_admin._apps:
        _firebase_app = firebase_admin.get_app()
        return

    cred = None
    creds_path = app.config.get("FIREBASE_CREDENTIALS_PATH")
    creds_json_str = app.config.get("FIREBASE_SERVICE_ACCOUNT_JSON")

    # Prioritas 1: Coba muat dari path file jika ada
    if creds_path:
        # Pastikan path file benar, relatif terhadap direktori utama proyek
        if os.path.exists(creds_path):
            try:
                cred = credentials.Certificate(creds_path)
                print(f"Memuat kredensial Firebase dari path: {creds_path}")
            except Exception as e:
                print(f"Peringatan: Gagal memuat kredensial dari file di path {creds_path}: {e}")
        else:
            print(f"Peringatan: File kredensial Firebase tidak ditemukan di path yang ditentukan: {creds_path}")

    # Prioritas 2: Coba muat dari JSON string jika path gagal atau tidak ada
    if not cred and creds_json_str:
        try:
            # Pastikan string tidak kosong dan merupakan JSON yang valid
            if creds_json_str.strip().startswith('{'):
                cred_dict = json.loads(creds_json_str)
                cred = credentials.Certificate(cred_dict)
                print("Memuat kredensial Firebase dari variabel lingkungan FIREBASE_SERVICE_ACCOUNT_JSON.")
            else:
                # Ini akan menangani kasus di mana variabel berisi email atau teks lain
                print("Peringatan: FIREBASE_SERVICE_ACCOUNT_JSON tidak berisi string JSON yang valid.")
        except json.JSONDecodeError as e:
            print(f"Peringatan: Gagal mem-parsing FIREBASE_SERVICE_ACCOUNT_JSON: {e}")
        except Exception as e:
            print(f"Peringatan: Gagal memuat kredensial dari FIREBASE_SERVICE_ACCOUNT_JSON: {e}")

    # Inisialisasi aplikasi jika kredensial berhasil dimuat
    if cred:
        try:
            _firebase_app = firebase_admin.initialize_app(cred)
            print("Firebase Admin SDK berhasil diinisialisasi.")
        except Exception as e:
            print(f"Error saat menginisialisasi Firebase Admin SDK: {e}")
    else:
        print("Peringatan: Tidak ada kredensial Firebase yang valid ditemukan. Notifikasi push dinonaktifkan.")