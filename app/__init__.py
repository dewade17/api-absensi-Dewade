from flask import Flask
from .config import load_config
from .extensions import cors, init_supabase, init_face_engine, init_firebase
from .middleware.error_handlers import register_error_handlers
from .blueprints.face.routes import face_bp
from .blueprints.absensi.routes import absensi_bp
from .blueprints.location.routes import location_bp
from .blueprints.notifications.routes import notif_bp

def create_app():
    app = Flask(__name__)
    load_config(app)
    from .db import timestamps 
    cors.init_app(app)
    init_supabase(app)
    init_face_engine(app)
    # Initialize Firebase Admin SDK (if configured). This must be called
    # after app.config is loaded but before sending any notifications.
    init_firebase(app)
    
    app.register_blueprint(face_bp)
    app.register_blueprint(absensi_bp)
    app.register_blueprint(location_bp)
    app.register_blueprint(notif_bp)

    register_error_handlers(app)

    @app.get("/health")
    def health():
        from .extensions import get_supabase
        return {
            "ok": True,
            "engine": app.config.get("MODEL_NAME"),
            "supabase": bool(get_supabase()),
            "bucket": app.config.get("SUPABASE_BUCKET")
        }

    return app

