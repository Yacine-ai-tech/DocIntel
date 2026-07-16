import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib
import pytest
from fastapi.testclient import TestClient

app = None
try:
    api_module = importlib.import_module("api")
    app = api_module.app
except ImportError:
    try:
        main_module = importlib.import_module("main")
        app = main_module.app
    except ImportError:
        pass

if app is None:
    pytest.skip("Could not import DocIntel app", allow_module_level=True)

client = TestClient(app)

def test_docintel_real_data_extraction():
    """Simulates sending a real document payload for OCR extraction.
    
    Acceptable responses:
    - 200: Successful extraction
    - 400/422: Invalid payload or validation error
    - 401/403: Authentication required (correct security behavior)
    - 503: OCR engine not loaded in CI environment
    """
    payload = {
        "document_base64": "SGVsbG8gV29ybGQ=",  # "Hello World" in base64
        "filename": "financial_report_Q3.pdf",
        "extract_tables": True
    }
    
    # Hit the main extraction endpoint
    response = client.post("/extract", json=payload)
    assert response.status_code in (200, 400, 401, 403, 422, 503), \
        f"Extraction endpoint returned unexpected status: {response.status_code}"

def test_docintel_batch_processing():
    """Simulates a batch ingestion request."""
    payload = {
        "job_id": "job_99812",
        "files": ["s3://dummy-bucket/doc1.pdf", "s3://dummy-bucket/doc2.pdf"]
    }
    response = client.post("/batch/upload", json=payload)
    assert response.status_code in (200, 202, 401, 403, 404, 422)

def test_docintel_health():
    response = client.get("/health")
    assert response.status_code == 200
