import os
from dotenv import load_dotenv

class BaseConfig:
    # Env & DB
    DATABASE_URL = os.getenv('DATABASE_URL', '')
    # Time & Geofence
    TIMEZONE = os.getenv('TIMEZONE', 'Asia/Makassar')
    DEFAULT_GEOFENCE_RADIUS = int(os.getenv('DEFAULT_GEOFENCE_RADIUS', '100'))
    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "e-hrm")
    MODEL_NAME = os.getenv("MODEL_NAME", "buffalo_l")
    SIGNED_URL_EXPIRES = int(os.getenv("SIGNED_URL_EXPIRES", "604800"))
    # Flask
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    JSON_SORT_KEYS = False

class DevConfig(BaseConfig):
    DEBUG = True

class ProdConfig(BaseConfig):
    DEBUG = False

def load_config(app):
    load_dotenv()
    env = os.getenv("FLASK_ENV", "development").lower()
    if env == "production":
        app.config.from_object(ProdConfig)
    else:
        app.config.from_object(DevConfig)
