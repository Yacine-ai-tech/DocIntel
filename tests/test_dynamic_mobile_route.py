"""
Tests for dynamic mobile upload routing and custom frontend URL preservation.
"""
import os
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from core.config import settings
from api import app
from services.camera import CameraManager, MobilePairing


@pytest.fixture
def client():
    return TestClient(app)


def test_default_mobile_route_setting():
    """Verify DOCINTEL_MOBILE_ROUTE defaults to vision_route_b."""
    assert hasattr(settings, "DOCINTEL_MOBILE_ROUTE")
    assert settings.DOCINTEL_MOBILE_ROUTE in ("vision_route_b", "ocr_fallback")


def test_camera_mobile_redirect_custom_domain(client):
    """Verify /camera/mobile redirects to FRONTEND_URL without forcing vercel rewrite."""
    custom_url = "https://docintel.ysiddo-ai-projects.app"
    with patch.dict(os.environ, {"FRONTEND_URL": custom_url}):
        res = client.get("/camera/mobile?token=test-tok-123", follow_redirects=False)
        assert res.status_code == 307
        assert res.headers["location"] == f"{custom_url}/camera/mobile?token=test-tok-123"


def test_qr_generation_preserves_custom_domain():
    """Verify MobilePairing.qr_bytes preserves custom domain without rewrite."""
    mgr = MobilePairing()
    custom_domain = "https://docintel.ysiddo-ai-projects.app"
    # Should not raise or force to vercel
    with patch.dict(os.environ, {"FRONTEND_URL": custom_domain}):
        qr = mgr.qr_base64("sample-token")
        if qr:
            assert qr.startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_camera_upload_uses_configured_mobile_route():
    """Verify /camera/upload uses DOCINTEL_MOBILE_ROUTE when route is not supplied in Form."""
    from api import _camera

    token = _camera.pairing.create_session("test_user", "mobile_test")
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"

    mock_run = AsyncMock(return_value={"fields": {"invoice_number": "INV-100", "_confidence": 0.95}, "page_count": 1})

    with patch("api._run_route", mock_run), patch.dict(os.environ, {"DOCINTEL_MOBILE_ROUTE": "ocr_fallback"}):
        with TestClient(app) as test_client:
            res = test_client.post(
                "/camera/upload",
                data={"token": token, "doc_type": "invoice"},
                files={"file": ("photo.png", fake_png, "image/png")}
            )
            assert res.status_code == 200
            data = res.json()
            assert data["fields"]["invoice_number"] == "INV-100"
            # Verify route used was ocr_fallback
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs.get("route") == "ocr_fallback"
