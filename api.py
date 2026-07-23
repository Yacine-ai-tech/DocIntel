"""
DocIntel API — Vision-first document AI pipeline.

Endpoints:
  GET  /health
  POST /extract          file + route (vision_premium|vision_local|ocr_fallback)
  POST /classify         file → doc_type only
  POST /classify-image   image + categories → category + confidence
  POST /extract-tables   PDF → tables list
  POST /extract-llm      text + doc_type → structured dict
  POST /batch/upload     list of files → job_id
  GET  /batch/{id}
  GET  /batch/{id}/results
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import settings
from core.logger import get_logger
from services.batch_processor import BatchProcessor
from services.llm_extractor import LLMExtractor
from services.vision_extractor import classify_image, extract_via_vision_llm

log = get_logger(__name__)

app = FastAPI(title="DocIntel", version="0.1.0",
              description="Vision-first document AI pipeline.")

# --- ETHICAL TELEMETRY ---
import threading
import requests
import os
import time
import uuid

def _send_telemetry():
    if os.environ.get("TELEMETRY_OPT_OUT", "").lower() in ("1", "true", "yes"):
        return
    
    lock_file = "/tmp/.ysiddo_telemetry.lock"
    try:
        if os.path.exists(lock_file):
            if time.time() - os.path.getmtime(lock_file) < 21600:
                return
        with open(lock_file, "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass

    try:
        if "log" in globals():
            globals()["log"].info("📡 Anonymous telemetry ENABLED (set TELEMETRY_OPT_OUT=true to disable).")
        else:
            import logging
            logging.info("📡 Anonymous telemetry ENABLED (set TELEMETRY_OPT_OUT=true to disable).")
            
        # WARM UP ML MODELS
        try:
            from services.surya_extractor import SuryaExtractor
            ex = SuryaExtractor()
            ex._ensure_models()
        except Exception as e:
            pass
        
        requests.post(
            "https://gateway.ysiddo-ai-projects.app/telemetry", 
            json={"service": "DocIntel", "event": "startup", "instance_id": str(uuid.getnode())[:8]},
            timeout=2
        )
    except Exception:
        pass

threading.Thread(target=_send_telemetry, daemon=True).start()
# -------------------------


from fastapi import Request
from fastapi.responses import JSONResponse
import os as _os

@app.middleware("http")
async def verify_internal_token(request: Request, call_next):
    # Allow health checks and public auth routes
    if request.url.path in ["/health", "/docs", "/openapi.json", "/api/redoc"] or request.url.path.startswith("/api/v1/auth/"):
        return await call_next(request)
        
    token = request.headers.get("X-OmniIntel-Internal-Token")
    expected_token = _os.environ.get("OMNIINTEL_INTERNAL_TOKEN", "default-dev-token")
    
    if token != expected_token and _os.environ.get("REQUIRE_INTERNAL_TOKEN", "true").lower() == "true":
        return JSONResponse(status_code=403, content={"detail": "Missing or invalid X-OmniIntel-Internal-Token"})
        
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



try:
    _assets_dir = _os.path.join(_os.path.dirname(__file__), "frontend", "dist", "assets")
    if _os.path.exists(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")
except Exception as e:
    log.warning("assets mount failed: %s", e)

batch = BatchProcessor(max_concurrency=settings.BATCH_MAX_CONCURRENCY)
# Route C text→JSON cleanup uses the cheaper model by default (cost-optimized).
extractor = LLMExtractor(model=settings.LLM_CLEANUP)


class ProcessResponse(BaseModel):
    doc_type: Optional[str] = None
    route: str
    confidence: Optional[float] = None
    page_count: Optional[int] = None
    processing_time_ms: Optional[float] = None
    fields: Optional[Dict[str, Any]] = None
    raw_text: Optional[str] = None
    error: Optional[str] = None


async def _run_route(data: bytes, route: str, doc_type: str) -> Dict[str, Any]:
    """Shared extraction core used by /extract, /process and batch.

    Handles PDFs as **multi-page**: vision routes get every page image (sent together so the
    model reasons across pages); the OCR route gets the full concatenated text. Returns
    {fields, page_count}.
    """
    from services.ocr_extractor import (
        extract_text_from_image, extract_text_from_pdf, is_pdf, pdf_page_count, pdf_to_pngs,
    )

    pdf = is_pdf(data)
    page_count = pdf_page_count(data) if pdf else 1

    if route in ("vision_premium", "vision_local"):
        model = settings.LLM_VISION_PREMIUM if route == "vision_premium" else settings.LLM_VISION_LOCAL
        images = pdf_to_pngs(data, max_pages=settings.MAX_PDF_PAGES) if pdf else [data]
        fields = None
        woke = False
        if images:
            try:
                fields = await extract_via_vision_llm(images, model=model, doc_type=doc_type)
                if isinstance(fields, dict) and fields.get("error"):
                    raise RuntimeError(str(fields["error"]))
            except Exception as e:
                log.warning("vision route %s failed (%s) — falling back to OCR extraction", route, e)
                fields = None
                if route == "vision_local":
                    # Route B runs on an on-demand Studio. Trigger a wake (non-blocking) so the
                    # NEXT request can use vision; this request degrades to OCR immediately.
                    try:
                        from services.lightning_studio import trigger_wake_async
                        woke = trigger_wake_async()
                    except Exception:
                        woke = False
        if fields is None:
            text = extract_text_from_pdf(data, max_pages=settings.MAX_PDF_PAGES) if pdf \
                else extract_text_from_image(data)
            if route == "vision_local":
                note = ("The local-vision inference Studio was asleep — I've started it (usually ready "
                        "in ~1-2 min). Extracted via OCR for now; re-run Route B shortly for full local "
                        "vision.") if woke else ("Local vision (Route B) was unavailable and the Studio "
                        "could not be woken (LIGHTNING creds missing/invalid). Extracted via OCR instead.")
            else:
                note = "Vision route was unavailable; extracted via OCR fallback."
            if text:
                fields = await extractor.extract(text, doc_type=doc_type)
                if isinstance(fields, dict):
                    fields.setdefault("_fallback_from", route)
                    fields.setdefault("_note", note)
                    if route == "vision_local":
                        fields.setdefault("_studio_waking", woke)
            else:
                fields = {"error": "extraction_unavailable",
                          "note": note + " OCR also recovered no text — try a clearer scan.",
                          "_fallback_from": route,
                          **({"_studio_waking": woke} if route == "vision_local" else {})}
    elif route == "ocr_fallback":
        text = extract_text_from_pdf(data, max_pages=settings.MAX_PDF_PAGES) if pdf \
            else extract_text_from_image(data)
        if not text:
            fields = {"error": "ocr_unavailable_or_empty",
                      "note": "No text recovered (ensure tesseract/poppler are installed)."}
        else:
            fields = await extractor.extract(text, doc_type=doc_type)
            if isinstance(fields, dict):
                fields["_ocr_chars"] = len(text)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown route: {route}")

    return {"fields": fields, "page_count": page_count}


def _confidence_of(fields: Any) -> Optional[float]:
    return fields.get("_confidence") if isinstance(fields, dict) else None


# ─────────────────────────────────────────────────────────────────────────────
# Marker-PDF Route A 
# ─────────────────────────────────────────────────────────────────────────────

from services.marker_extractor import MarkerExtractor
_marker = MarkerExtractor()

@app.post("/extract/marker")
async def extract_marker(file: UploadFile = File(...)):
    """Route A explicit: Convert PDF to Markdown via Marker."""
    import tempfile
    import os
    suffix = ".pdf" if file.filename.lower().endswith(".pdf") else ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        data = await file.read()
        tmp.write(data)
        tmp_path = tmp.name
    try:
        res = _marker.convert(tmp_path)
    finally:
        os.remove(tmp_path)
    return res

# ─────────────────────────────────────────────────────────────────────────────
# Camera QR / Mobile Uploads
# ─────────────────────────────────────────────────────────────────────────────

from services.camera import CameraManager
_camera = CameraManager()

@app.post("/camera/pair")
async def camera_pair(user: str = Form("demo_user"), device: str = Form("Mobile")):
    """Generate a pairing token and QR base64 for mobile uploads."""
    return _camera.pair_mobile(user, device)

@app.get("/camera/qr/{token}")
async def camera_qr_image(token: str):
    """Return raw QR code image bytes for a token."""
    qr_bytes = _camera.pairing.qr_bytes(token)
    if not qr_bytes:
        raise HTTPException(404, "Token not found or QR failed")
    from fastapi.responses import Response
    return Response(content=qr_bytes, media_type="image/png")

@app.post("/camera/upload")
async def camera_upload(token: str = Form(...), file: UploadFile = File(...), doc_type: str = Form("default")):
    """Mobile device uploads photo; processes via vision local route."""
    session = _camera.validate_mobile(token)
    if not session:
        raise HTTPException(403, "Invalid or expired token")
    data = await file.read()
    _camera.record_mobile_upload(token)
    # Automatically route to vision
    return await _run_route(data, route="vision_local", doc_type=doc_type)

# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def dashboard():
    """Serve the DocIntel UI at the root — the built SPA when present, else the legacy demo."""
    import os
    root = os.path.dirname(__file__)
    spa = os.path.join(root, "frontend", "dist", "index.html")
    if os.path.exists(spa):
        return FileResponse(spa)
    return {"service": "docintel", "docs": "/docs"}


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "docintel", "version": "0.1.0"}


@app.post("/classify", response_model=ProcessResponse)
async def classify(file: UploadFile = File(...)) -> ProcessResponse:
    """Fast doc-type classification — content-based (a text sample + the same classifier
    ``/process`` uses), falling back to a filename heuristic when content is inconclusive."""
    data = await file.read()
    doc_type: Optional[str] = None
    confidence: Optional[float] = None
    # 1) Content-based classification (matches /process behaviour).
    try:
        from services.ocr_extractor import (
            DocumentClassifier, extract_text_from_image, extract_text_from_pdf, is_pdf,
        )
        sample = extract_text_from_pdf(data, max_pages=2) if is_pdf(data) else extract_text_from_image(data)
        if sample and sample.strip():
            detected, conf = DocumentClassifier.classify_document(sample)
            doc_type = {"report": "financial_report", "general": "default"}.get(detected, detected)
            confidence = conf
    except Exception as e:
        log.warning("content classify failed, falling back to filename: %s", e)
    # 2) Filename heuristic — a strong, cheap signal. Compute it, then combine.
    name = (file.filename or "").lower()
    fname_type: Optional[str] = None
    fname_conf: Optional[float] = None
    if any(k in name for k in ("invoice", "inv")):
        fname_type, fname_conf = "invoice", 0.85
    elif any(k in name for k in ("contract", "agreement")):
        fname_type, fname_conf = "contract", 0.8
    elif any(k in name for k in ("receipt",)):
        fname_type, fname_conf = "receipt", 0.8
    elif any(k in name for k in ("report", "statement")):
        fname_type, fname_conf = "financial_report", 0.7
    # Prefer a confident filename match when the content signal is missing, 'default',
    # or low-confidence (the text heuristic is weak on scanned/short docs).
    weak_content = (not doc_type) or (doc_type == "default") or ((confidence or 0.0) < 0.6)
    if weak_content and fname_type:
        doc_type, confidence = fname_type, fname_conf
    elif not doc_type:
        doc_type, confidence = "default", 0.5
    return ProcessResponse(doc_type=doc_type, route="classify", confidence=confidence)


@app.post("/classify-image")
async def classify_image_endpoint(
    file: UploadFile = File(...),
    categories: str = Form(...),
) -> Dict[str, Any]:
    """
    Vision-first object classification (auction-listing pattern).

    `categories` is a comma-separated string, e.g. "tractor,lathe,crane".
    """
    cats = [c.strip() for c in categories.split(",") if c.strip()]
    if not cats:
        raise HTTPException(status_code=400, detail="categories required")
    img = await file.read()
    t0 = time.time()
    result = await classify_image(img, cats)
    result["processing_time_ms"] = round((time.time() - t0) * 1000, 1)
    return result


@app.post("/extract", response_model=ProcessResponse)
async def extract(
    file: UploadFile = File(...),
    route: str = Form("vision_premium"),
    doc_type: str = Form("invoice"),
) -> ProcessResponse:
    """
    Full extraction pipeline with 3 routes (multi-page PDFs handled end-to-end):
      - vision_premium  (Claude Sonnet 4.6 Vision)
      - vision_local    (Ollama Llama 3.2 Vision)
      - ocr_fallback    (Tesseract OCR + LLM cleanup)
    """
    t0 = time.time()
    data = await file.read()
    out = await _run_route(data, route, doc_type)
    return ProcessResponse(
        doc_type=doc_type,
        route=route,
        fields=out["fields"],
        confidence=_confidence_of(out["fields"]),
        page_count=out["page_count"],
        processing_time_ms=round((time.time() - t0) * 1000, 1),
    )


@app.post("/process", response_model=ProcessResponse)
async def process(
    file: UploadFile = File(...),
    route: str = Form("vision_premium"),
    doc_type: str = Form("auto"),
) -> ProcessResponse:
    """
    One-shot pipeline: upload → (auto-classify) → multi-page extract → structured JSON.

    `doc_type="auto"` content-classifies the document first (text-based heuristic), then runs
    the chosen route. Tables are included for PDFs. Returns doc_type, fields, confidence,
    page_count.
    """
    t0 = time.time()
    data = await file.read()

    from services.ocr_extractor import (
        DocumentClassifier, extract_text_from_image, extract_text_from_pdf, is_pdf,
    )
    if doc_type == "auto":
        sample = extract_text_from_pdf(data, max_pages=2) if is_pdf(data) \
            else extract_text_from_image(data)
        detected, _cls_conf = DocumentClassifier.classify_document(sample or "")
        # Map the classifier's labels onto the extractor's schema keys.
        doc_type = {"report": "financial_report", "general": "default"}.get(detected, detected)

    out = await _run_route(data, route, doc_type)
    fields = out["fields"]
    if isinstance(fields, dict) and is_pdf(data):
        try:
            import io as _io
            import pdfplumber
            with pdfplumber.open(_io.BytesIO(data)) as pdf:
                tcount = sum(len(p.extract_tables() or []) for p in pdf.pages)
            fields.setdefault("_tables_detected", tcount)
        except Exception:
            import logging; logging.error('Unhandled exception', exc_info=True)
            pass

    return ProcessResponse(
        doc_type=doc_type,
        route=route,
        fields=fields,
        confidence=_confidence_of(fields),
        page_count=out["page_count"],
        processing_time_ms=round((time.time() - t0) * 1000, 1),
    )


@app.post("/extract-llm", response_model=ProcessResponse)
async def extract_llm(text: str = Form(...), doc_type: str = Form("invoice")) -> ProcessResponse:
    t0 = time.time()
    fields = await extractor.extract(text, doc_type=doc_type)
    return ProcessResponse(
        doc_type=doc_type,
        route="ocr_fallback",
        fields=fields,
        processing_time_ms=round((time.time() - t0) * 1000, 1),
    )


@app.post("/extract-tables")
async def extract_tables(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Extract tables from a PDF via pdfplumber (table detection only)."""
    try:
        import pdfplumber
        import io
        pdf_bytes = await file.read()
        tables: List[Any] = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables() or []
                tables.extend(page_tables)
        return {"tables": tables, "table_count": len(tables)}
    except ImportError:
        return {"error": "pdfplumber_not_installed", "tables": []}
    except Exception as e:
        log.exception("extract_tables failed: %s", e)
        return {"error": str(e), "tables": []}


@app.post("/batch/upload")
async def batch_upload(
    background: BackgroundTasks,
    files: List[UploadFile] = File(...),
    route: str = Form("vision_premium"),
    doc_type: str = Form("invoice"),
) -> Dict[str, Any]:
    """Start a background batch process and return a job_id."""
    file_data: List[Dict[str, Any]] = []
    for f in files:
        file_data.append({
            "filename": f.filename,
            "bytes": await f.read(),
            "doc_type": doc_type,
            "route": route,
        })

    job_id = batch.new_job(total=len(file_data))

    async def _process_one(fd: Dict[str, Any]) -> Dict[str, Any]:
        out = await _run_route(fd["bytes"], fd["route"], fd["doc_type"])
        return {
            "filename": fd["filename"],
            "fields": out["fields"],
            "confidence": _confidence_of(out["fields"]),
            "page_count": out["page_count"],
        }

    background.add_task(batch.process, job_id, file_data, _process_one)
    return {"job_id": job_id, "total": len(file_data)}


@app.get("/batch/{job_id}")
async def batch_status(job_id: str) -> Dict[str, Any]:
    status = batch.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="job_not_found")
    return status


@app.get("/batch/{job_id}/results")
async def batch_results(job_id: str) -> Dict[str, Any]:
    results = batch.get_results(job_id)
    if results is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return {"job_id": job_id, "results": results}


