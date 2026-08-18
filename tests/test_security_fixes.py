"""Regression tests for the security/reliability audit findings fixed this session.

Each test is named after (and directly verifies) one specific finding, so a future
regression in any of these shows up as a named, specific failure rather than a
generic "something broke."
"""
import io
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from api import app

client = TestClient(app)

TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c63f8cfc0000003010100c9fe92ef0000000049454e44ae426082"
)


def _set_internal_token(monkeypatch, token: str = "test-secret-token"):
    monkeypatch.setenv("REQUIRE_INTERNAL_TOKEN", "true")
    monkeypatch.setenv("DOCINTEL_INTERNAL_TOKEN", token)
    return token


# ─── F-01: REQUIRE_INTERNAL_TOKEN must actually protect the routes that matter ──

def test_require_internal_token_actually_blocks_extract(monkeypatch):
    _set_internal_token(monkeypatch)
    resp = client.post("/extract", files={"file": ("x.png", TINY_PNG, "image/png")},
                        data={"route": "vision_route_a"})
    assert resp.status_code == 403


def test_require_internal_token_actually_blocks_batch_upload(monkeypatch):
    _set_internal_token(monkeypatch)
    resp = client.post("/batch/upload", files={"files": ("x.png", TINY_PNG, "image/png")})
    assert resp.status_code == 403


def test_require_internal_token_actually_blocks_camera_pair(monkeypatch):
    _set_internal_token(monkeypatch)
    resp = client.post("/camera/pair", data={"user": "alice"})
    assert resp.status_code == 403


def test_require_internal_token_allows_with_correct_token(monkeypatch):
    """The flag must still let a correctly-authenticated caller through — a test
    that only checks rejection could pass even if the header were being ignored
    outright, not just enforced."""
    token = _set_internal_token(monkeypatch)
    resp = client.post("/camera/pair", data={"user": "alice"},
                        headers={"X-DocIntel-Internal-Token": token})
    assert resp.status_code == 200


def test_require_internal_token_still_allows_health_and_docs(monkeypatch):
    """Genuinely public routes must stay reachable even when hardening is on —
    the fix narrowed the bypass list, it shouldn't have narrowed it to nothing."""
    _set_internal_token(monkeypatch)
    assert client.get("/health").status_code in (200, 503)  # 503 only if LOGS_DIR isn't writable
    assert client.get("/docs").status_code == 200


# ─── F-03: webhook_url SSRF ──────────────────────────────────────────────────

def test_webhook_url_rejects_private_ip():
    resp = client.post(
        "/batch/upload",
        files={"files": ("x.png", TINY_PNG, "image/png")},
        data={"webhook_url": "https://169.254.169.254/latest/meta-data/"},
    )
    assert resp.status_code == 400
    assert "non-public" in resp.json()["detail"] or "resolve" in resp.json()["detail"]


def test_webhook_url_rejects_loopback():
    resp = client.post(
        "/batch/upload",
        files={"files": ("x.png", TINY_PNG, "image/png")},
        data={"webhook_url": "https://127.0.0.1:8080/hook"},
    )
    assert resp.status_code == 400


def test_webhook_url_rejects_non_https_scheme():
    resp = client.post(
        "/batch/upload",
        files={"files": ("x.png", TINY_PNG, "image/png")},
        data={"webhook_url": "http://example.com/hook"},
    )
    assert resp.status_code == 400
    assert "https" in resp.json()["detail"]


def test_webhook_url_accepts_valid_public_https():
    """A real, resolvable, public HTTPS URL must not be rejected — the point is
    blocking SSRF targets, not breaking the legitimate use case."""
    from services.webhook import _validate_webhook_url
    _validate_webhook_url("https://example.com/webhook")  # must not raise


# ─── F-11: upload size cap ───────────────────────────────────────────────────

def test_extract_rejects_oversized_upload(monkeypatch):
    # _MAX_UPLOAD_BYTES is computed once from settings at import time, not re-read
    # per request — patch the module constant directly rather than the env var,
    # which a reload wouldn't actually propagate into it anyway (core.config's
    # `settings` singleton is cached across reloads of api.py).
    import api as api_module
    monkeypatch.setattr(api_module, "_MAX_UPLOAD_BYTES", 1024)  # 1KB cap
    oversized = b"\x00" * 4096  # 4KB, well over the 1KB cap just set
    resp = client.post("/extract", files={"file": ("big.bin", oversized, "application/octet-stream")},
                        data={"route": "ocr_fallback"})
    assert resp.status_code == 413


def test_small_upload_is_not_rejected():
    """The cap must not accidentally reject ordinary small files."""
    resp = client.post("/classify", files={"file": ("tiny.png", TINY_PNG, "image/png")})
    assert resp.status_code != 413


# ─── F-20: constant-time token comparison ────────────────────────────────────

def test_internal_token_comparison_uses_constant_time_compare():
    """Code-inspection-style regression test: asserts the middleware actually
    calls secrets.compare_digest rather than a plain == / `in` check, guarding
    against someone reintroducing a timing side-channel later. Not a timing
    measurement (unreliable in CI) — a real assertion on the actual code path."""
    import inspect
    import api as api_module
    src = inspect.getsource(api_module.verify_internal_token)
    assert "compare_digest" in src


# ─── F-14: multi-language classifier ─────────────────────────────────────────

def test_classify_non_english_document():
    from services.ocr_extractor import DocumentClassifier
    text = "Facture N° 30064443\nMontant dû: 34,73 EUR"
    doc_type, confidence = DocumentClassifier.classify_document(text)
    assert doc_type == "invoice"
    assert confidence > 0.3  # better than the old "general, 0.3" catch-all


def test_classify_english_document_still_works():
    """Regression guard: adding French keywords must not break the existing
    English classification this was already correct on."""
    from services.ocr_extractor import DocumentClassifier
    text = "INVOICE #12345\nAmount due: $100.00\nPayment terms: Net 30"
    doc_type, confidence = DocumentClassifier.classify_document(text)
    assert doc_type == "invoice"
    assert confidence > 0.3


# ─── F-04: merge_doc_fields partial-failure signal ───────────────────────────
# (Direct unit tests for this live in tests/test_doc_merge.py, alongside the
# rest of that module's tests — see test_errored_chunks_dropped_but_signaled
# and test_partial_failure_signaled_even_with_only_one_surviving_chunk.)


# ─── F-06 / F-08: batch job persistence + TTL eviction ───────────────────────

def test_batch_jobs_are_evicted_after_ttl(monkeypatch, tmp_path):
    monkeypatch.setenv("BATCH_JOB_TTL_SECONDS", "1")
    import importlib
    import services.batch_processor as bp_module
    importlib.reload(bp_module)
    # Force the JSON-file backend regardless of whether POSTGRES_URL is configured
    # in this environment's .env — this test is specifically about file-based
    # eviction under an isolated tmp_path, not the real (possibly production) DB.
    monkeypatch.setattr(bp_module.db, "DB_ENABLED", False)
    bp_module._STATE_DIR = tmp_path / "batch_jobs"
    bp = bp_module.BatchProcessor()
    job_id = bp.new_job(total=1)
    assert bp.get_status(job_id) is not None
    time.sleep(1.2)
    bp.new_job(total=1)  # any new_job() call sweeps expired entries
    assert bp.get_status(job_id) is None
    importlib.reload(bp_module)  # restore defaults for subsequent tests


@pytest.mark.asyncio
async def test_batch_job_state_survives_process_restart(tmp_path, monkeypatch):
    import importlib
    import services.batch_processor as bp_module
    importlib.reload(bp_module)
    monkeypatch.setattr(bp_module.db, "DB_ENABLED", False)
    bp_module._STATE_DIR = tmp_path / "batch_jobs"

    bp1 = bp_module.BatchProcessor(max_concurrency=2)
    job_id = bp1.new_job(total=1)

    async def _proc(fd):
        return {"ok": True}

    await bp1.process(job_id, [{"filename": "a"}], _proc)
    assert bp1.get_status(job_id)["status"] == "completed"

    # Simulate a restart: a brand new BatchProcessor instance, same state dir.
    bp2 = bp_module.BatchProcessor(max_concurrency=2)
    recovered = bp2.get_status(job_id)
    assert recovered is not None
    assert recovered["status"] == "completed"
    assert bp2.get_results(job_id)[0]["ok"] is True
    importlib.reload(bp_module)


def test_camera_sessions_are_evicted_after_expiry(monkeypatch, tmp_path):
    monkeypatch.setenv("CAMERA_SESSION_TTL_SECONDS", "1")
    import importlib
    import services.camera as camera_module
    importlib.reload(camera_module)
    monkeypatch.setattr(camera_module.db, "DB_ENABLED", False)
    camera_module._STATE_DIR = tmp_path / "camera_sessions"
    pairing = camera_module.MobilePairing()
    token = pairing.create_session("alice")
    assert pairing.get_status(token) is not None
    time.sleep(1.2)
    pairing.create_session("bob")  # any create_session() call sweeps expired entries
    assert pairing.get_status(token) is None
    importlib.reload(camera_module)


# ─── F-17: /health checks a real dependency ──────────────────────────────────

def test_health_endpoint_reports_checks():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "checks" in body
    assert "logs_dir_writable" in body["checks"]


def test_health_endpoint_reflects_real_dependency_failure(monkeypatch):
    """Break the one real dependency /health checks (LOGS_DIR writability) and
    confirm it actually reports non-200 — previously this endpoint was an
    unconditional 200 regardless of any real failure."""
    import api as api_module
    from core.config import settings

    bad_dir = "/nonexistent-path-for-health-check-test-xyz"
    monkeypatch.setattr(settings, "LOGS_DIR", bad_dir)
    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["checks"]["logs_dir_writable"] is False
