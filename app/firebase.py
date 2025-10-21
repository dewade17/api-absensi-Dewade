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
                print(f"Peringatan: GOOGLE_APPLICATIONS_CREDENTIALS menunjuk ke file yang tidak ada: {cred_path}")

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
            # Dicari beberapa lokasi kredensial default:
            # 1. Di direktori yang sama dengan file ini
            # 2. Di direktori induk (root aplikasi)
            possible_names = [
                'e-hrm-1e3e0-firebase-adminsdk-fbsvc-d9feba4316.json'
            ]
            found = False
            base_dirs = [os.path.dirname(__file__), os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))]
            for base in base_dirs:
                for name in possible_names:
                    candidate = os.path.join(base, name)
                    if os.path.exists(candidate):
                        try:
                            cred = credentials.Certificate(candidate)
                            firebase_admin.initialize_app(cred)
                            print(f"Firebase Admin SDK diinisialisasi dari berkas default: {candidate}.")
                            found = True
                            return
                        except Exception as e:
                            print(f"Peringatan: Gagal menginisialisasi Firebase dari berkas default {candidate}: {e}")
                            found = True
                            break
                if found:
                    break
            # Jika semua metode gagal, berikan peringatan.
            if not found:
                print("Peringatan: Kredensial Firebase Admin tidak lengkap dan berkas default tidak ditemukan. Notifikasi push akan dinonaktifkan.")

    except Exception as e:
        print(f"Kesalahan saat menginisialisasi Firebase Admin SDK: {e}")
