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
