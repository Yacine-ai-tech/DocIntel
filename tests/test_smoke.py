"""Smoke tests for DocIntel."""
import pytest
from fastapi.testclient import TestClient


def test_imports():
    """All key modules import cleanly."""
    from core import config, logger
    from services import llm_extractor, vision_extractor, marker_extractor, batch_processor
    assert config.settings is not None
    assert logger.get_logger is not None


def test_app_creates():
    """FastAPI app instantiates without error."""
    from api import app
    assert app is not None
    assert app.title == "DocIntel"


def test_health_endpoint():
    """GET /health returns 200 OK."""
    from api import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "docintel"


def test_classify_endpoint_no_file():
    """POST /classify without file returns 422."""
    from api import app
    client = TestClient(app)
    r = client.post("/classify")
    assert r.status_code in (401, 403, 422)  # 422=validation, 401/403=auth required


def test_batch_processor_lifecycle(monkeypatch, tmp_path):
    """BatchProcessor: new job → status → results."""
    import services.batch_processor as bp_module
    # Force the JSON-file backend for isolation, regardless of whether this
    # environment's .env has a real POSTGRES_URL configured — a smoke test must
    # not write to (and leave rows in) a real database.
    monkeypatch.setattr(bp_module.db, "DB_ENABLED", False)
    monkeypatch.setattr(bp_module, "_STATE_DIR", tmp_path / "batch_jobs")
    bp = bp_module.BatchProcessor()
    job_id = bp.new_job(total=3)
    status = bp.get_status(job_id)
    assert status["status"] == "pending"
    assert status["total"] == 3
    results = bp.get_results(job_id)
    assert results == [None, None, None]  # index-aligned slots; None = not yet processed


def test_llm_extractor_instantiates():
    """LLMExtractor can be instantiated."""
    from services.llm_extractor import LLMExtractor
    ex = LLMExtractor()
    assert ex.model
