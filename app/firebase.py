import os
import firebase_admin
from firebase_admin import credentials
import json

def initialize_firebase():
    """
    Menginisialisasi Firebase Admin SDK menggunakan variabel lingkungan.
    Ini aman untuk dipanggil beberapa kali.
    """
    # Cek apakah aplikasi Firebase default sudah diinisialisasi
    if firebase_admin._apps:
        return

    try:
        # Prioritas 1: Menggunakan file kredensial JSON jika path-nya ditentukan
        cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if cred_path:
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                print("Firebase Admin SDK diinisialisasi dari file GOOGLE_APPLICATION_CREDENTIALS.")
                return
            else:
                print(f"Peringatan: GOOGLE_APPLICATION_CREDENTIALS menunjuk ke file yang tidak ada: {cred_path}")

        # Prioritas 2: Menggunakan variabel lingkungan terpisah (seperti di proyek Next.js)
        project_id = os.getenv('FIREBASE_PROJECT_ID')
        client_email = os.getenv('FIREBASE_CLIENT_EMAIL')
        private_key = os.getenv('FIREBASE_PRIVATE_KEY')

        if all([project_id, client_email, private_key]):
            # Ganti escape sequence '\n' dengan newline character
            private_key_formatted = private_key.replace('\\n', '\n')
            
            cred_dict = {
                "type": "service_account",
                "project_id": project_id,
                "private_key": private_key_formatted,
                "client_email": client_email,
                "token_uri": "https://oauth2.googleapis.com/token", # URI default
            }
            
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("Firebase Admin SDK diinisialisasi dari variabel lingkungan.")
        else:
            # Prioritas 3: Cek apakah ada berkas kredensial bawaan di dalam proyek.
            default_cred_path = os.path.join(os.path.dirname(__file__), 'e-hrm-2d3fe-firebase-adminsdk-fbsvc-3a0eb724d6.json')
            if os.path.exists(default_cred_path):
                try:
                    cred = credentials.Certificate(default_cred_path)
                    firebase_admin.initialize_app(cred)
                    print("Firebase Admin SDK diinisialisasi dari berkas default.")
                    return
                except Exception as e:
                    print(f"Peringatan: Gagal menginisialisasi Firebase dari berkas default: {e}")
            # Jika semua metode gagal, berikan peringatan.
            print("Peringatan: Kredensial Firebase Admin tidak lengkap dan berkas default tidak ditemukan. Notifikasi push akan dinonaktifkan.")

    except Exception as e:
        print(f"Kesalahan saat menginisialisasi Firebase Admin SDK: {e}")
