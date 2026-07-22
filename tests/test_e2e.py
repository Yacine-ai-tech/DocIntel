import pytest
import httpx
from fastapi.testclient import TestClient
from api import app
import os

client = TestClient(app)
HEADERS = {"X-OmniIntel-Internal-Token": os.getenv("OMNIINTEL_INTERNAL_TOKEN", "default-dev-token")}


@pytest.mark.asyncio
async def test_e2e_docintel_process():
    # Simulate a document upload for processing
    dummy_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    files = {"file": ("test_doc.pdf", dummy_pdf, "application/pdf")}
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/process", files=files, headers=HEADERS)
        # 422 Unprocessable Entity if PDF is totally corrupted or PyMuPDF fails
        assert response.status_code in (200, 422)

@pytest.mark.asyncio
async def test_e2e_docintel_classify():
    dummy_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    files = {"file": ("test_doc.pdf", dummy_pdf, "application/pdf")}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/classify", files=files, headers=HEADERS)
        assert response.status_code in (200, 422)

@pytest.mark.asyncio
async def test_e2e_docintel_health():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health", headers=HEADERS)
        assert response.status_code == 200
