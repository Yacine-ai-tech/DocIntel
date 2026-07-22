import pytest
import httpx
from fastapi.testclient import TestClient
from api.server import app
import os

client = TestClient(app)
HEADERS = {"X-OmniIntel-Internal-Token": os.getenv("OMNIINTEL_INTERNAL_TOKEN", "REDACTED_SECRET")}

@pytest.mark.asyncio
async def test_e2e_docintel_upload_and_index():
    # Simulate a document upload
    dummy_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    files = {"file": ("test_doc.pdf", dummy_pdf, "application/pdf")}
    data = {"collection": "knowledge_base", "chunk_size": 1000}
    
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/v1/documents/upload", data=data, files=files, headers=HEADERS)
        # It should return 200, or 422 if the PDF is too corrupted for PyMuPDF
        assert response.status_code in (200, 422)

@pytest.mark.asyncio
async def test_e2e_docintel_search():
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/v1/documents/search", json={"query": "financial statements", "top_k": 3}, headers=HEADERS)
        assert response.status_code == 200
        assert "results" in response.json()

@pytest.mark.asyncio
async def test_e2e_docintel_collection_stats():
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/collections/stats", headers=HEADERS)
        assert response.status_code == 200
        assert "document_count" in response.json()
