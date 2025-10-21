# flask_api_face/app/__init__.py

from flask import Flask
from .config import load_config
from . import extensions
from .middleware.error_handlers import register_error_handlers

# Import blueprints
from .blueprints.face.routes import face_bp
from .blueprints.absensi.routes import absensi_bp
from .blueprints.location.routes import location_bp
from .blueprints.notifications.routes import notif_bp

def create_app():
    app = Flask(__name__)
    load_config(app)

    # Initialize extensions (Celery binding, Supabase, Firebase, etc.)
    extensions.init_app(app)

    # Register blueprints DENGAN url_prefix yang jelas
    app.register_blueprint(face_bp, url_prefix="/api/face")
    app.register_blueprint(absensi_bp, url_prefix="/api/absensi")
    app.register_blueprint(location_bp, url_prefix="/api/location")
    app.register_blueprint(notif_bp, url_prefix="/api/notifications")

    # Error handlers
    register_error_handlers(app)

    @app.get("/health")
    def health():
        from .extensions import get_supabase
        return {
            "ok": True,
            "engine": app.config.get("MODEL_NAME"),
            "supabase": bool(get_supabase()),
            "bucket": app.config.get("SUPABASE_BUCKET"),
        }

    return app
