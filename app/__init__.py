import os
from flask import Flask
from dotenv import load_dotenv

# Muat variabel lingkungan dari .env
load_dotenv()

def create_app(config_class=None):
    """
    Factory function untuk membuat instance aplikasi Flask.
    """
    app = Flask(__name__)

    # Konfigurasi aplikasi
    if config_class is None:
        app.config.from_object('app.config.Config')
    else:
        app.config.from_object(config_class)

    # Inisialisasi ekstensi
    from .extensions import db
    db.init_app(app)

    # Inisialisasi Firebase Admin SDK
    from .firebase import initialize_firebase
    with app.app_context():
        initialize_firebase()

    # Registrasi middleware
    from .middleware.error_handlers import register_error_handlers
    register_error_handlers(app)

    # Registrasi blueprint
    from .blueprints.face.routes import face_bp
    from .blueprints.absensi.routes import absensi_bp
    from .blueprints.location.routes import location_bp
    from .blueprints.notifications.routes import notifications_bp

    app.register_blueprint(face_bp, url_prefix='/api/face')
    app.register_blueprint(absensi_bp, url_prefix='/api/absensi')
    app.register_blueprint(location_bp, url_prefix='/api/location')
    app.register_blueprint(notifications_bp, url_prefix='/api/notifications')


    return app
