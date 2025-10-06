from flask import Flask
from .config import load_config
from .extensions import db, cors, init_supabase, init_face_engine, init_firebase
from .middleware.error_handlers import register_error_handlers
from .blueprints.face.routes import face_bp
from .blueprints.absensi.routes import absensi_bp
from .blueprints.location.routes import location_bp
from .blueprints.notifications.routes import notif_bp

def create_app():
    app = Flask(__name__)
    load_config(app)
    
    # Inisialisasi ekstensi dengan app
    db.init_app(app)
    cors.init_app(app)

    # Inisialisasi layanan
    init_supabase(app)
    init_face_engine(app)
    init_firebase(app)
    
    # Impor model atau modul yang bergantung pada app context di sini jika perlu
    from .db import timestamps 

    # Daftarkan blueprint
    app.register_blueprint(face_bp, url_prefix="/api/face")
    app.register_blueprint(absensi_bp)
    app.register_blueprint(location_bp)
    app.register_blueprint(notif_bp)

    # Daftarkan error handler
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