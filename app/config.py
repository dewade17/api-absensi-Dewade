# flask_api_face/app/config.py

import os
from dotenv import load_dotenv

# Panggil load_dotenv() di awal untuk memuat file .env
load_dotenv()

class BaseConfig:
    # Nilai default atau placeholder
    DATABASE_URL = ''
    TIMEZONE = 'Asia/Makassar'
    DEFAULT_GEOFENCE_RADIUS = 100
    SUPABASE_URL = ""
    SUPABASE_SERVICE_ROLE_KEY = ""
    SUPABASE_BUCKET = "e-hrm"
    MODEL_NAME = "buffalo_l"
    SIGNED_URL_EXPIRES = 604800
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    JSON_SORT_KEYS = False
    
    # Konfigurasi Celery
    CELERY_BROKER_URL = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

    # Placeholder untuk Firebase
    FIREBASE_PROJECT_ID = None
    FIREBASE_CLIENT_EMAIL = None
    FIREBASE_PRIVATE_KEY = None

class DevConfig(BaseConfig):
    DEBUG = True

class ProdConfig(BaseConfig):
    DEBUG = False

def load_config(app):
    """Memuat konfigurasi berdasarkan lingkungan dan variabel .env."""
    env = os.getenv("FLASK_ENV", "development").lower()
    if env == "production":
        app.config.from_object(ProdConfig)
    else:
        app.config.from_object(DevConfig)
    
    # Muat variabel dari .env secara eksplisit ke dalam app.config.
    # Ini menimpa nilai default di BaseConfig jika ada di .env.
    app.config.update(
        DATABASE_URL = os.getenv('DATABASE_URL', ''),
        TIMEZONE = os.getenv('TIMEZONE', 'Asia/Makassar'),
        DEFAULT_GEOFENCE_RADIUS = int(os.getenv('DEFAULT_GEOFENCE_RADIUS', '100')),
        SUPABASE_URL = os.getenv("SUPABASE_URL", ""),
        SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        
        # Variabel Celery
        CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),

        # Variabel Firebase
        FIREBASE_PROJECT_ID=os.getenv('FIREBASE_PROJECT_ID'),
        FIREBASE_CLIENT_EMAIL=os.getenv('FIREBASE_CLIENT_EMAIL'),
        FIREBASE_PRIVATE_KEY=os.getenv('FIREBASE_PRIVATE_KEY'),
    )