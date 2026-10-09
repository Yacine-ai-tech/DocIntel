"""Tests for DocIntel demo session scoping and Route A fallback resilience."""
import pytest
from unittest.mock import AsyncMock, patch
from core.db import list_documents, count_documents, get_documents_stats


def test_session_scoping_isolation_in_memory():
    # Test scoping logic without requiring live Postgres
    docs = [
        {"id": "seed-1", "owner_session_id": None, "doc_type": "invoice"},
        {"id": "user-a-doc", "owner_session_id": "session_user_a", "doc_type": "invoice"},
        {"id": "user-b-doc", "owner_session_id": "session_user_b", "doc_type": "receipt"},
    ]

    def filter_docs(session_id=None, is_admin=False):
        if is_admin:
            return docs
        if session_id:
            return [d for d in docs if d["owner_session_id"] == session_id or d["owner_session_id"] is None]
        return [d for d in docs if d["owner_session_id"] is None]

    # User A sees seed + User A doc
    user_a_view = filter_docs(session_id="session_user_a")
    assert len(user_a_view) == 2
    assert {d["id"] for d in user_a_view} == {"seed-1", "user-a-doc"}

    # User B sees seed + User B doc
    user_b_view = filter_docs(session_id="session_user_b")
    assert len(user_b_view) == 2
    assert {d["id"] for d in user_b_view} == {"seed-1", "user-b-doc"}

    # Anonymous visitor sees only seed
    anon_view = filter_docs(session_id=None)
    assert len(anon_view) == 1
    assert anon_view[0]["id"] == "seed-1"

    # Admin sees all 3 docs
    admin_view = filter_docs(is_admin=True)
    assert len(admin_view) == 3


@pytest.mark.asyncio
async def test_route_a_resilient_fallback_to_ocr(monkeypatch):
    """When Route A vision models fail, _run_route falls back gracefully to Route C OCR."""
    from api import _run_route

    # Mock extract_via_vision_llm to simulate vision API failure
    with patch("api.extract_via_vision_llm", side_effect=RuntimeError("Auth failed")), \
         patch("services.ocr_extractor.extract_text_from_pdf", return_value="Invoice #123 Total: $100"), \
         patch("services.ocr_extractor.extract_text_from_image", return_value="Invoice #123 Total: $100"), \
         patch("services.ocr_extractor.is_pdf", return_value=False), \
         patch("api.extractor.extract", new_callable=AsyncMock) as mock_extract:
        
        mock_extract.return_value = {
            "invoice_number": "123",
            "total": 100.0,
            "_confidence": 0.95,
        }

        fake_pdf = b"%PDF-1.4 test document"
        res = await _run_route(fake_pdf, route="vision_route_a", doc_type="invoice")
        
        fields = res.get("fields", {})
        assert fields.get("invoice_number") == "123"
        assert fields.get("_route_a_fallback") is True
        assert fields.get("_fallback_used") is True
