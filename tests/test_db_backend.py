"""Regression tests for the Postgres-backed persistence path (core/db.py).

conftest.py clears POSTGRES_URL for the whole test session so the rest of the
suite never touches a real database. These tests explicitly opt back in — read
the real connection string straight out of .env (not the process environment,
which conftest already cleared), skip cleanly if this checkout has none
configured (e.g. CI, or a self-hoster's clone), and clean up every row they
write regardless of pass/fail so repeated local runs never accumulate test
data in a real database.
"""
import importlib
from pathlib import Path

import pytest

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _real_postgres_url() -> str:
    if not _ENV_PATH.exists():
        return ""
    for line in _ENV_PATH.read_text().splitlines():
        if line.startswith("POSTGRES_URL="):
            return line.split("=", 1)[1].strip()
    return ""


REAL_URL = _real_postgres_url()
pytestmark = pytest.mark.skipif(not REAL_URL, reason="no POSTGRES_URL configured in .env")


@pytest.fixture
def db_module(monkeypatch):
    """Activate the real POSTGRES_URL for one test, and clean up every table
    this test suite writes to afterward — even on failure.

    Mutates the shared core.config.settings singleton's attribute and
    core.db.DB_ENABLED directly via monkeypatch, rather than
    importlib.reload(core.config) — every other already-imported module
    (api.py included) did `from core.config import settings` at ITS OWN
    import time, binding the same singleton *object*; reloading core.config
    would rebind core.config.settings to a brand-new object that nothing
    else observes, silently breaking any other test that patches settings
    attributes later in the same session (confirmed: this broke
    test_health_endpoint_reflects_real_dependency_failure when it ran after
    this fixture, because api.py's /health handler was still reading the
    pre-reload settings instance). Mutating the existing object's attributes
    has no such problem — every module sees the same change.
    """
    from core.config import settings
    monkeypatch.setattr(settings, "POSTGRES_URL", REAL_URL)
    import core.db as db_module
    monkeypatch.setattr(db_module, "DB_ENABLED", True)
    monkeypatch.setattr(db_module, "_schema_ready", False)
    monkeypatch.setattr(db_module, "_pool", None)
    import sys
    if "api" in sys.modules:
        monkeypatch.setattr(sys.modules["api"], "DB_ENABLED", True)
    try:
        db_module.ensure_schema()
    except Exception as e:
        pytest.skip(f"Neon Postgres unreachable from test environment: {e}")
    try:
        yield db_module
    finally:
        try:
            with db_module.get_conn() as conn:
                conn.execute("DELETE FROM docintel_documents WHERE id LIKE 'pytest-%'")
                conn.execute("DELETE FROM batch_results WHERE job_id LIKE 'pytest-%'")
                conn.execute("DELETE FROM batch_jobs WHERE id LIKE 'pytest-%'")
                conn.execute("DELETE FROM camera_sessions WHERE token LIKE 'pytest-%'")
                conn.commit()
        except Exception:
            pass
        pool = db_module._pool
        if pool is not None:
            try:
                pool.close()
            except Exception:
                pass


def test_batch_job_round_trip_against_real_postgres(db_module):
    db_module.upsert_batch_job({
        "id": "pytest-job-1", "status": "completed", "total": 2, "processed": 1,
        "failed": 1, "webhook_url": None,
        "created_at": "2026-08-16T00:00:00Z", "updated_at": "2026-08-16T00:00:01Z",
        "started_at": "2026-08-16T00:00:00Z", "finished_at": "2026-08-16T00:00:01Z",
    })
    db_module.upsert_batch_result("pytest-job-1", 0, {"filename": "a.pdf", "fields": {"total": 42.0}})
    db_module.upsert_batch_result("pytest-job-1", 1, {"error": "bad file", "filename": "b.pdf"})

    jobs = db_module.load_all_batch_jobs()
    assert "pytest-job-1" in jobs
    job = jobs["pytest-job-1"]
    assert job["status"] == "completed"
    assert job["results"][0]["fields"]["total"] == 42.0
    assert job["results"][1]["error"] == "bad file"

    db_module.delete_batch_job("pytest-job-1")
    assert "pytest-job-1" not in db_module.load_all_batch_jobs()


def test_camera_session_round_trip_against_real_postgres(db_module):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    db_module.upsert_camera_session("pytest-token-1", {
        "user": "pytest_user", "device_name": "Test Device", "created_at": now,
        "expires_at": now + timedelta(hours=1), "uploads": 3,
        "last_upload": now, "last_result": {"fields": {"vendor": "ACME"}}, "active": True,
    })

    sessions = db_module.load_all_camera_sessions()
    assert "pytest-token-1" in sessions
    session = sessions["pytest-token-1"]
    assert session["user"] == "pytest_user"
    assert session["uploads"] == 3
    assert session["last_result"]["fields"]["vendor"] == "ACME"

    db_module.delete_camera_session("pytest-token-1")
    assert "pytest-token-1" not in db_module.load_all_camera_sessions()


@pytest.mark.asyncio
async def test_batch_processor_uses_db_backend_end_to_end(db_module, monkeypatch):
    """The actual BatchProcessor class, not just core.db directly — confirms the
    service-layer wiring (services/batch_processor.py) picks the DB path when
    DB_ENABLED, persists incrementally, and a fresh instance recovers state."""
    import services.batch_processor as bp_module
    importlib.reload(bp_module)
    assert bp_module.db.DB_ENABLED

    bp1 = bp_module.BatchProcessor(max_concurrency=2)
    # Force a predictable, cleanable job id instead of a random uuid4.
    job_id = "pytest-bp-job-1"
    bp1._jobs[job_id] = {
        "id": job_id, "status": "pending", "total": 1, "processed": 0, "failed": 0,
        "results": [None], "created_at": bp_module._now(), "updated_at": bp_module._now(),
    }
    bp1._persist(job_id)

    async def _proc(fd):
        return {"ok": True}

    await bp1.process(job_id, [{"filename": "a"}], _proc)
    assert bp1.get_status(job_id)["status"] == "completed"

    # Simulate a restart: a brand-new instance loads state from Postgres, not memory.
    bp2 = bp_module.BatchProcessor(max_concurrency=2)
    recovered = bp2.get_status(job_id)
    assert recovered is not None
    assert recovered["status"] == "completed"
    importlib.reload(bp_module)


def test_document_record_round_trip_against_real_postgres(db_module):
    """Verify storing, retrieving, counting, and deleting document records."""
    doc_id = "pytest-doc-1"
    res_id = db_module.upsert_document({
        "id": doc_id,
        "filename": "invoice_123.pdf",
        "file_size": 20480,
        "mime_type": "application/pdf",
        "doc_type": "invoice",
        "route": "vision_route_a",
        "confidence": 0.96,
        "page_count": 3,
        "processing_time_ms": 1150.0,
        "fields": {"invoice_id": "INV-123", "amount": 500.0},
        "raw_text": "INVOICE INV-123 Total: $500.00",
        "status": "completed",
        "owner_session_id": "pytest_sess_1",
    })
    assert res_id == doc_id

    doc = db_module.get_document(doc_id)
    assert doc is not None
    assert doc["filename"] == "invoice_123.pdf"
    assert doc["doc_type"] == "invoice"
    assert doc["fields"]["amount"] == 500.0
    assert doc["confidence"] == 0.96

    docs = db_module.list_documents(doc_type="invoice", search="INV-123")
    assert any(d["id"] == doc_id for d in docs)

    count = db_module.count_documents(doc_type="invoice")
    assert count >= 1

    deleted = db_module.delete_document(doc_id)
    assert deleted is True
    assert db_module.get_document(doc_id) is None


def test_document_stats_and_filtering(db_module):
    """Verify aggregate statistics generation from Postgres."""
    db_module.upsert_document({
        "id": "pytest-doc-stats-1",
        "filename": "contract.pdf",
        "doc_type": "contract",
        "route": "vision_route_a",
        "confidence": 0.92,
        "page_count": 5,
        "processing_time_ms": 1500.0,
        "owner_session_id": "pytest_sess_stats",
    })
    db_module.upsert_document({
        "id": "pytest-doc-stats-2",
        "filename": "receipt.png",
        "doc_type": "receipt",
        "route": "ocr_fallback",
        "confidence": 0.88,
        "page_count": 1,
        "processing_time_ms": 500.0,
        "owner_session_id": "pytest_sess_stats",
    })

    stats = db_module.get_documents_stats(owner_session_id="pytest_sess_stats")
    assert stats["total_documents"] == 2
    assert stats["successful_documents"] == 2
    assert stats["total_pages"] == 6
    assert stats["by_doc_type"].get("contract") == 1
    assert stats["by_doc_type"].get("receipt") == 1
    assert stats["avg_confidence"] == 0.9


def test_document_api_endpoints_round_trip(db_module):
    """Verify FastAPI document endpoints (/api/documents, /api/documents/stats)."""
    from fastapi.testclient import TestClient
    from api import app

    client = TestClient(app)

    db_module.upsert_document({
        "id": "pytest-doc-api-1",
        "filename": "annual_report.pdf",
        "doc_type": "financial_report",
        "route": "vision_route_a",
        "confidence": 0.95,
        "page_count": 10,
        "processing_time_ms": 2200.0,
        "fields": {"revenue": 1000000},
    })

    resp = client.get("/api/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(d["id"] == "pytest-doc-api-1" for d in data["documents"])

    stats_resp = client.get("/api/documents/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_documents"] >= 1

    single_resp = client.get("/api/documents/pytest-doc-api-1")
    assert single_resp.status_code == 200
    assert single_resp.json()["filename"] == "annual_report.pdf"

    del_resp = client.delete("/api/documents/pytest-doc-api-1")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

