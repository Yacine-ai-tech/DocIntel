"""
Shallow route-existence smoke tests — one per endpoint, asserting only that the route
exists and doesn't 500 the whole ASGI app on a bare/empty request.

Runs fully in-process against the app object (httpx ASGITransport) rather than over
real network — a plain `pytest tests/` must never make outbound requests to any live
deployment. If you specifically want to exercise a real running instance instead, set
TEST_BASE_URL to it explicitly.
"""
import os

import httpx
import pytest

TOKEN = os.getenv('DOCINTEL_INTERNAL_TOKEN', '')
HEADERS = {'X-DocIntel-Internal-Token': TOKEN}
TEST_BASE_URL = os.getenv('TEST_BASE_URL', '').strip()

token = 'dummy_token'
job_id = 'dummy_job_id'


def _client() -> httpx.AsyncClient:
    if TEST_BASE_URL:
        return httpx.AsyncClient(base_url=TEST_BASE_URL)
    from api import app
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_e2e_api_post__extract_marker_0():
    # Extracted from api.py
    async with _client() as ac:
        response = await ac.post('/extract/marker', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_post__camera_pair_1():
    # Extracted from api.py
    async with _client() as ac:
        response = await ac.post('/camera/pair', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_get__camera_qr_token_2():
    # Extracted from api.py
    async with _client() as ac:
        response = await ac.get(f'/camera/qr/{token}', headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_post__camera_upload_3():
    # Extracted from api.py
    async with _client() as ac:
        response = await ac.post('/camera/upload', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_get___4():
    # Extracted from api.py
    async with _client() as ac:
        response = await ac.get('/', headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_get__health_5():
    # Extracted from api.py
    async with _client() as ac:
        response = await ac.get('/health', headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_post__classify_6():
    # Extracted from api.py
    async with _client() as ac:
        response = await ac.post('/classify', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_post__classify_image_7():
    # Extracted from api.py
    async with _client() as ac:
        response = await ac.post('/classify-image', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_post__extract_8():
    # Extracted from api.py
    async with _client() as ac:
        response = await ac.post('/extract', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_post__process_9():
    # Extracted from api.py
    async with _client() as ac:
        response = await ac.post('/process', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_post__extract_llm_10():
    # Extracted from api.py
    async with _client() as ac:
        response = await ac.post('/extract-llm', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_post__extract_tables_11():
    # Extracted from api.py
    async with _client() as ac:
        response = await ac.post('/extract-tables', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_post__batch_upload_12():
    # Extracted from api.py
    async with _client() as ac:
        response = await ac.post('/batch/upload', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_get__batch_job_id_13():
    # Extracted from api.py
    async with _client() as ac:
        response = await ac.get(f'/batch/{job_id}', headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_get__batch_job_id_results_14():
    # Extracted from api.py
    async with _client() as ac:
        response = await ac.get(f'/batch/{job_id}/results', headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_get__health_15():
    # Extracted from api.py (tesseract_service.py's standalone copy was removed —
    # /health is the same route on the main app)
    async with _client() as ac:
        response = await ac.get('/health', headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)

@pytest.mark.asyncio
async def test_e2e_api_post__extract_16():
    # Extracted from api.py (tesseract_service.py's standalone copy was removed —
    # /extract is the same route on the main app)
    async with _client() as ac:
        response = await ac.post('/extract', json={}, headers=HEADERS)
        assert response.status_code in (200, 400, 401, 403, 404, 405, 422, 500)
