from typing import Optional
from flask_cors import CORS
from supabase import create_client, Client
from flask import current_app
from insightface.app import FaceAnalysis

cors = CORS()

_supabase: Optional[Client] = None
_engine: Optional[FaceAnalysis] = None

def init_supabase(app):
    global _supabase
    url = app.config.get("SUPABASE_URL")
    key = app.config.get("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        _supabase = create_client(url, key)

def get_supabase() -> Optional[Client]:
    return _supabase

def init_face_engine(app):
    global _engine
    model = app.config.get("MODEL_NAME", "buffalo_l")
    engine = FaceAnalysis(name=model, providers=["CPUExecutionProvider"])
    engine.prepare(ctx_id=0)
    _engine = engine

def get_face_engine() -> FaceAnalysis:
    if _engine is None:
        model = current_app.config.get("MODEL_NAME", "buffalo_l")
        engine = FaceAnalysis(name=model, providers=["CPUExecutionProvider"])
        engine.prepare(ctx_id=0)
        return engine
    return _engine

# -----------------------------------------------------------------------------
# Firebase Admin initialization
# -----------------------------------------------------------------------------
# The `_firebase_app` global holds the initialized Firebase app instance. It is
# configured in ``init_firebase``. If firebase_admin is not installed or no
# credential is provided, notifications will be silently disabled.
_firebase_app = None

def init_firebase(app):
    """Initialize Firebase Admin SDK if credentials are provided.

    This function looks for the following configuration keys on ``app.config``:

    - ``FIREBASE_SERVICE_ACCOUNT_JSON``: A JSON string containing the service
      account credentials.
    - ``FIREBASE_CREDENTIALS_PATH``: Path to a JSON file with service
      account credentials.

    If either is present and firebase_admin can be imported, a Firebase
    application will be initialized and stored in the module-level
    ``_firebase_app`` variable. Subsequent calls are no-ops.
    """
    global _firebase_app
    if _firebase_app is not None:
        return
    try:
        from firebase_admin import credentials, initialize_app  # type: ignore
    except Exception:
        # firebase_admin is not installed; skip initialization.
        return

    import json

    creds_json = app.config.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    creds_path = app.config.get("FIREBASE_CREDENTIALS_PATH")
    cred = None
    if creds_json:
        try:
            data = json.loads(creds_json)
            cred = credentials.Certificate(data)
        except Exception:
            cred = None
    if cred is None and creds_path:
        try:
            cred = credentials.Certificate(creds_path)
        except Exception:
            cred = None
    if cred is not None:
        _firebase_app = initialize_app(cred)
