"""
DocIntel API — Vision-first document AI pipeline.

Endpoints:
  GET  /health
  POST /extract          file + route (vision_route_a|vision_route_b|ocr_fallback)
  POST /classify         file → doc_type only
  POST /classify-image   image + categories → category + confidence
  POST /extract-tables   PDF → tables list
  POST /extract-fields   file → generic form label/value pairs
  POST /extract-llm      text + doc_type → structured dict
  POST /batch/upload     list of files → job_id (optional webhook_url callback on completion)
  GET  /batch/{id}
  GET  /batch/{id}/results
  POST /camera/pair      desktop → pairing token + QR (phone opens /camera/mobile?token=...)
  GET  /camera/qr/{token} raw QR PNG
  POST /camera/upload    phone → photo → Route B extraction, stored on the session
  GET  /camera/status/{token} desktop polling target for the phone's upload result
"""
from __future__ import annotations

import asyncio
import json
import os
import os as _os
import secrets as _secrets
import threading
import time
import uuid as _uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import settings
from core.logger import get_logger
from services.batch_processor import BatchProcessor
from services.camera import CameraManager
from services.llm_extractor import LLMExtractor
from services.marker_extractor import MarkerExtractor
from services.webhook import WebhookURLRejected, _validate_webhook_url

# Optional: if this checkout sits alongside a shared logging helper in a sibling
# directory (not part of this repo, absent on a standalone clone), hook into it
# for centralized log aggregation. No-ops cleanly otherwise.
try:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "global_scripts"))
    from omni_logging import get_logger as get_workspace_logger
    workspace_logger = get_workspace_logger("DocIntel")
except ImportError:
    workspace_logger = None

from services.vision_extractor import classify_image, extract_via_vision_llm

log = get_logger(__name__)

app = FastAPI(title="DocIntel", version="0.1.0",
              description="Vision-first document AI pipeline.")


def _warm_up_models():
    """Pre-load Surya OCR models at startup so the first real request isn't slow.
    Runs regardless of TELEMETRY_OPT_OUT — unrelated to telemetry."""
    try:
        from services.surya_extractor import SuryaExtractor
        SuryaExtractor()._ensure_models()
    except Exception:
        pass


def _telemetry_instance_id() -> str:
    """
    A random, locally-generated install ID — NOT derived from MAC address or any other
    hardware fingerprint. Persisted under LOGS_DIR so repeat startups of the same install
    report the same ID (for dedup on the receiving end); delete the file to reset it.
    See TELEMETRY.md for why this is a random UUID rather than a hardware-derived value.
    """
    id_file = os.path.join(settings.LOGS_DIR, ".telemetry_instance_id")
    try:
        if os.path.exists(id_file):
            existing = open(id_file).read().strip()
            if existing:
                return existing
    except Exception:
        pass
    new_id = _uuid.uuid4().hex[:16]
    try:
        with open(id_file, "w") as f:
            f.write(new_id)
    except Exception:
        pass
    return new_id


def _send_telemetry():
    """
    One anonymous startup ping per ~6h to TELEMETRY_URL, so the project can count distinct
    installs. Sends only {service, event, instance_id} — no document content, filenames,
    IPs, or other request data. Disable entirely with TELEMETRY_OPT_OUT=true.
    """

    if os.environ.get("TELEMETRY_OPT_OUT", "").lower() in ("1", "true", "yes"):
        return

    lock_file = os.path.join(settings.LOGS_DIR, ".telemetry_last_ping")
    try:
        if os.path.exists(lock_file) and time.time() - os.path.getmtime(lock_file) < 21600:
            return
        with open(lock_file, "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass

    try:
        import httpx
        telemetry_url = os.environ.get(
            "TELEMETRY_URL", "https://gateway.ysiddo-ai-projects.app/telemetry"
        )
        log.info("Anonymous telemetry ping to %s (set TELEMETRY_OPT_OUT=true to disable).", telemetry_url)
        httpx.post(
            telemetry_url,
            json={"service": "DocIntel", "event": "startup", "instance_id": _telemetry_instance_id()},
            timeout=2,
        )
    except Exception:
        pass


threading.Thread(target=_warm_up_models, daemon=True).start()
threading.Thread(target=_send_telemetry, daemon=True).start()
# -------------------------

# Genuinely public: static assets, health/docs, and the homepage. Everything
# that costs money or touches user data (extraction, classification, batch,
# camera) is intentionally NOT here — REQUIRE_INTERNAL_TOKEN is opt-in and
# defaults to false, so this list only matters once an operator has
# explicitly asked for hardening, at which point "expensive route requires
# the token" is the whole point, not a trap to route around. (Previously
# /extract, /classify*, /process, and the entire /camera/ and /batch/
# prefixes were bypassed here regardless of the flag — REQUIRE_INTERNAL_TOKEN
# protected almost nothing that actually mattered. Any server-to-server
# integration — n8n, a workflow automation tool, another service you run —
# should send X-OmniIntel-Internal-Token like any other caller once
# hardening is on.)
_PUBLIC_PATHS = {
    "/", "/health", "/benchmarks", "/docs", "/openapi.json", "/api/redoc",
    "/favicon.png", "/favicon.ico", "/mark.png", "/logo.png",
}
_PUBLIC_PREFIXES = ("/api/v1/auth/", "/assets/", "/static/")


@app.middleware("http")
async def verify_internal_token(request: Request, call_next):
    is_options = request.method == "OPTIONS"
    is_public_path = request.url.path in _PUBLIC_PATHS
    is_public_prefix = request.url.path.startswith(_PUBLIC_PREFIXES)
    if is_options or is_public_path or is_public_prefix:
        return await call_next(request)

    req_token_setting = _os.environ.get("REQUIRE_INTERNAL_TOKEN", "false").lower()
    if req_token_setting in ("true", "1", "yes"):
        correct_token = _os.environ.get("OMNIINTEL_INTERNAL_TOKEN", "")
        token = request.headers.get("X-OmniIntel-Internal-Token", "")
        auth_h = request.headers.get("Authorization", "")
        bearer_token = auth_h[len("Bearer "):] if auth_h.startswith("Bearer ") else ""
        header_token_ok = _secrets.compare_digest(token, correct_token)
        bearer_token_ok = _secrets.compare_digest(bearer_token, correct_token)
        if not correct_token or not (header_token_ok or bearer_token_ok):
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

_MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


async def _read_upload(file: UploadFile) -> bytes:
    """Read an uploaded file's bytes with a size cap.

    Every upload route used to read the whole body in one bare call — no
    Content-Length check, no cap — buffering the entire upload into memory
    regardless of size.
    An oversized upload (or many concurrent ones, especially via unauthenticated
    routes) could exhaust process memory. Reads in chunks so a request can be
    rejected as soon as it exceeds the cap, without ever buffering the full
    oversized body first.
    """
    chunks: List[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB upload limit",
            )
        chunks.append(chunk)
    return b"".join(chunks)


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

    Routes:
      - vision_route_a: Claude Sonnet 4.6 Vision via LiteLLM (premium, no fallback)
      - vision_route_b: Ollama vision model — local (this machine) or remote (hardware you
                        control, same network or reachable over the internet). Never a
                        third-party inference API. Configured via ROUTE_B_MODE + OLLAMA_MODEL.
                        Auto-fallback to Route C (OCR) on any failure.
      - ocr_fallback:   Tesseract OCR + LLM cleanup (Route C)
    """
    from services.ocr_extractor import (
        extract_text_from_image, extract_text_from_pdf, is_pdf, pdf_page_count, pdf_to_pngs,
    )

    pdf = is_pdf(data)
    page_count = pdf_page_count(data) if pdf else 1
    used_route = route
    fallback_used = False

    # Route A: Claude Sonnet 4.6 Vision (no fallback)
    if route == "vision_route_a":
        model = settings.LLM_VISION_ROUTE_A
        images = pdf_to_pngs(data, max_pages=settings.MAX_PDF_PAGES) if pdf else [data]
        fields = None
        if images:
            try:
                log.info("Route A: Attempting extraction with Claude Sonnet 4.6 Vision")
                fields = await extract_via_vision_llm(images, model=model, doc_type=doc_type)
                if isinstance(fields, dict) and fields.get("error"):
                    raise RuntimeError(str(fields["error"]))
                log.info("Route A: Extraction succeeded")
            except Exception as e:
                log.error(f"Route A failed: {e}")
                fields = {"error": f"Route A extraction failed: {e}"}
        if fields is None:
            fields = {"error": "Route A extraction failed"}

    # Route B: Ollama vision (local GPU or remote Ollama-compatible endpoint)
    elif route == "vision_route_b":
        mode = os.getenv("ROUTE_B_MODE", "local")
        model_tag = os.getenv("OLLAMA_MODEL", "qwen2.5vl:7b")
        log.info("Route B: mode=%s model=%s", mode, model_tag)

        if workspace_logger:
            workspace_logger.log_route_selection("vision_route_b", f"{mode}/{model_tag}")

        images = pdf_to_pngs(data, max_pages=settings.MAX_PDF_PAGES) if pdf else [data]
        fields = None

        if images:
            try:
                fields = await extract_via_vision_llm(images, doc_type=doc_type, route_b=True)
                if isinstance(fields, dict) and fields.get("_route_b_failed"):
                    raise RuntimeError(str(fields.get("error", "route_b_failed")))
                log.info("Route B (%s/%s): extraction succeeded", mode, model_tag)
            except Exception as e:
                log.warning("Route B (%s/%s) failed: %s — falling back to Route C (OCR)", mode, model_tag, e)
                fallback_used = True
                used_route = "ocr_fallback"

                if workspace_logger:
                    workspace_logger.log_fallback("vision_route_b", "ocr_fallback", f"{mode}/{model_tag} failed: {e}")

        if fields is None or fallback_used:
            log.info("Route C: Using OCR fallback (Tesseract + LLM cleanup)")
            text = extract_text_from_pdf(data, max_pages=settings.MAX_PDF_PAGES) if pdf \
                else extract_text_from_image(data)
            if text:
                fields = await extractor.extract(text, doc_type=doc_type)
                if isinstance(fields, dict):
                    fields["_route_b_fallback"] = True
                    fields["_route_b_mode"] = mode
                    fields["_route_b_model"] = model_tag
                    fields["_route_c_used"] = True
                else:
                    fields = {"error": "OCR extraction failed", "_route_b_fallback": True,
                              "_route_b_mode": mode, "_route_b_model": model_tag}
            else:
                fields = {"error": "No text extracted for OCR", "_route_b_fallback": True,
                          "_route_b_mode": mode, "_route_b_model": model_tag}

    # Route C: OCR fallback
    elif route == "ocr_fallback":
        log.info("Route C: Using OCR fallback (Tesseract + LLM cleanup)")
        text = extract_text_from_pdf(data, max_pages=settings.MAX_PDF_PAGES) if pdf \
            else extract_text_from_image(data)
        if text:
            fields = await extractor.extract(text, doc_type=doc_type)
        else:
            fields = {"error": "No text extracted for OCR"}

    # Legacy route names for backward compatibility
    elif route in ("vision_premium", "vision_local"):
        log.warning(f"Legacy route name '{route}' used, mapping to new architecture")
        if workspace_logger:
            workspace_logger.log_fallback(route, "vision_route_a" if route == "vision_premium" else "vision_route_b", "Legacy route name mapping")

        if route == "vision_premium":
            return await _run_route(data, "vision_route_a", doc_type)
        else:
            return await _run_route(data, "vision_route_b", doc_type)

    else:
        raise ValueError(f"Unknown route: {route}")

    if isinstance(fields, dict) and fields.get("error"):
        fields["_used_route"] = used_route
        fields["_fallback_used"] = fallback_used
    elif isinstance(fields, dict):
        fields["_used_route"] = used_route
        fields["_fallback_used"] = fallback_used

    return {"fields": fields, "page_count": page_count}


def _confidence_of(fields: Any) -> Optional[float]:
    return fields.get("_confidence") if isinstance(fields, dict) else None


# ─────────────────────────────────────────────────────────────────────────────
# Marker-PDF Route A
# ─────────────────────────────────────────────────────────────────────────────

_marker = MarkerExtractor()


@app.post("/extract/marker")
async def extract_marker(file: UploadFile = File(...)):
    """Route A explicit: Convert PDF to Markdown via Marker."""
    import tempfile
    import os
    suffix = ".pdf" if file.filename.lower().endswith(".pdf") else ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        data = await _read_upload(file)
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
    """Mobile device uploads photo; processes via Route B (local/self-hosted Ollama vision),
    and stores the result on the session so the desktop side that generated the QR can pick
    it up via GET /camera/status/{token} — see /camera/status below."""
    session = _camera.validate_mobile(token)
    if not session:
        raise HTTPException(403, "Invalid or expired token")
    data = await _read_upload(file)
    t0 = time.time()
    out = await _run_route(data, route="vision_route_b", doc_type=doc_type)
    result = {
        "fields": out["fields"],
        "confidence": _confidence_of(out["fields"]),
        "page_count": out["page_count"],
        "processing_time_ms": round((time.time() - t0) * 1000, 1),
    }
    _camera.record_mobile_upload(token, result)
    return result


@app.get("/camera/status/{token}")
async def camera_status(token: str) -> Dict[str, Any]:
    """Desktop polling target: has the paired phone uploaded anything yet, and what did
    extraction return. Poll this after /camera/pair while showing the QR code."""
    status = _camera.get_mobile_status(token)
    if status is None:
        raise HTTPException(404, "Token not found")
    return status

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
    # DocIntel has no database — LOGS_DIR/UPLOADS_DIR writability is the one real
    # runtime dependency worth checking; every route that persists anything
    # (telemetry state, uploaded files) needs it. Previously this endpoint was an
    # unconditional 200 with no dependency check at all — Docker's HEALTHCHECK and
    # CI's e2e-smoke both rely on it as their signal the service is actually fine.
    checks: Dict[str, bool] = {}
    try:
        probe = Path(settings.LOGS_DIR) / ".health_write_probe"
        probe.write_text(str(time.time()))
        probe.unlink(missing_ok=True)
        checks["logs_dir_writable"] = True
    except Exception:
        checks["logs_dir_writable"] = False

    ok = all(checks.values())
    body = {"status": "ok" if ok else "degraded", "service": "docintel", "version": "0.1.0", "checks": checks}
    # curl -f (Dockerfile's HEALTHCHECK) and most uptime monitors only look at the
    # HTTP status, not the JSON body — a degraded check has to be a real non-2xx.
    return body if ok else JSONResponse(status_code=503, content=body)


@app.get("/benchmarks")
async def benchmarks() -> Dict[str, Any]:
    """Serves eval/BENCHMARK.md's real numbers to the frontend's /benchmarks and /benchmark
    pages, read from disk on every request. Both pages used to carry their own hand-copied
    snapshot of these numbers (one a curated summary, one a literal copy-paste of the whole
    file) with nothing forcing them to stay in sync with each other or with the real benchmark
    as it's re-run over time. This is the fix: one endpoint, reading the same two files a human
    auditing the benchmark would read, so the UI can't drift from them the way the old hardcoded
    copies already had.
    """
    root = Path(__file__).resolve().parent
    summary: Dict[str, Any] = {}
    summary_path = root / "eval" / "benchmark_summary.json"
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text())
        except Exception:
            log.exception("Failed to parse eval/benchmark_summary.json")

    markdown = None
    md_path = root / "eval" / "BENCHMARK.md"
    if md_path.exists():
        try:
            markdown = md_path.read_text()
        except Exception:
            log.exception("Failed to read eval/BENCHMARK.md")

    return {"summary": summary, "markdown": markdown}


@app.post("/classify", response_model=ProcessResponse)
async def classify(file: UploadFile = File(...)) -> ProcessResponse:
    """Fast doc-type classification — content-based (a text sample + the same classifier
    ``/process`` uses), falling back to a filename heuristic when content is inconclusive."""
    data = await _read_upload(file)
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
    # French filename keywords added alongside the English ones — same gap as
    # DocumentClassifier's content keywords (services/ocr_extractor.py), same fix.
    if any(k in name for k in ("invoice", "inv", "facture")):
        fname_type, fname_conf = "invoice", 0.85
    elif any(k in name for k in ("contract", "agreement", "contrat", "accord")):
        fname_type, fname_conf = "contract", 0.8
    elif any(k in name for k in ("receipt", "recu", "reçu")):
        fname_type, fname_conf = "receipt", 0.8
    elif any(k in name for k in ("report", "statement", "rapport")):
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
    img = await _read_upload(file)
    t0 = time.time()
    result = await classify_image(img, cats)
    result["processing_time_ms"] = round((time.time() - t0) * 1000, 1)
    return result


async def _extract_text_core(data: bytes, route: str, max_pages: int) -> Dict[str, Any]:
    """Shared by /extract/text (sync) and /extract/text/batch (async job) below — same
    logic, same {text, method, page_count, chars} shape, one code path to keep in sync.

      route="auto"     Marker if installed, else the native/OCR text layer
      route="marker"   Marker only (errors if not installed)
      route="ocr"      pdfplumber native text layer, per-page Tesseract for scans

    Images always go through OCR (no text layer to read).
    """
    from services.ocr_extractor import (
        extract_text_from_image, extract_text_from_pdf, extract_text_native_office,
        is_pdf, pdf_page_count,
    )
    t0 = time.time()
    pdf = is_pdf(data)
    pages = pdf_page_count(data) if pdf else 1
    limit = max_pages or settings.MAX_PDF_PAGES
    text, method = "", ""

    # PPTX/DOCX/XLSX are ZIP archives of XML with real text runs, not renderable
    # images — routing them into extract_text_from_image made PIL raise
    # "cannot identify image file" (caught, silently returns ''), which is why
    # these previously came back at 20-40 chars instead of a real transcript.
    # Checked before the pdf branch: None here means "not this format", not
    # "no text", so a genuine PDF/image still falls through normally below.
    if not pdf:
        office_text = extract_text_native_office(data)
        if office_text is not None:
            return {
                "text": office_text, "method": "native_office", "page_count": pages,
                "chars": len(office_text),
                "processing_time_ms": round((time.time() - t0) * 1000, 1),
            }

    if pdf and route in ("auto", "marker"):
        import tempfile
        import os as _o
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            # marker-pdf is CPU-bound and can run minutes on a long document — off the
            # event loop so one big document doesn't stall every other request this
            # process is handling.
            res = await asyncio.to_thread(_marker.convert, tmp_path)
        finally:
            _o.remove(tmp_path)
        md = (res or {}).get("markdown") or ""
        if md.strip():
            text, method = md, "marker"
        elif route == "marker":
            return {"text": "", "method": "marker", "page_count": pages, "chars": 0,
                    "error": (res or {}).get("error", "marker_failed")}

    if not text:
        text = await asyncio.to_thread(extract_text_from_pdf, data, max_pages=limit) if pdf \
            else await asyncio.to_thread(extract_text_from_image, data)
        method = "native_or_ocr" if pdf else "ocr"

    return {
        "text": text,
        "method": method,
        "page_count": pages,
        "chars": len(text),
        "processing_time_ms": round((time.time() - t0) * 1000, 1),
    }


@app.post("/extract/text")
async def extract_text(
    file: UploadFile = File(...),
    route: str = Form("auto"),
    max_pages: int = Form(0),
) -> Dict[str, Any]:
    """Full document text — the RAG-ingestion path, synchronous.

    Every other extraction endpoint returns *typed fields* (invoice-shaped: vendor,
    total, line_items...). That is the wrong shape for a RAG consumer, which needs the
    document's actual prose — a structured-text intermediate to ingest into RAG. Marker is
    the ideal tool for this, but marker-pdf is a heavy optional dependency, so this endpoint
    uses whichever text path is actually available. See _extract_text_core for the routes.

    A synchronous call to this endpoint on a large/complex document can outlast a
    reverse-proxy's edge timeout even though the extraction itself would have
    succeeded — see /extract/text/batch below for the async path built for exactly
    that case.
    """
    data = await _read_upload(file)
    return await _extract_text_core(data, route, max_pages)


@app.post("/extract/text/batch")
async def extract_text_batch(
    background: BackgroundTasks,
    files: List[UploadFile] = File(...),
    route: str = Form("auto"),
    max_pages: int = Form(0),
    webhook_url: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Async equivalent of /extract/text for documents too large/slow to finish inside a
    synchronous request. /batch/upload already exists for this pattern but only ever ran
    the /process structured-extraction path — a large document needing Marker (route=
    auto/marker) had no async option, only OCR's usually-faster-but-lower-quality text
    layer, which is the wrong tradeoff to force just to dodge a timeout. Poll the same
    way as /batch/upload: GET /batch/{job_id} for status, GET /batch/{job_id}/results
    for the {text, method, page_count, chars} shape per file once complete."""
    if webhook_url:
        try:
            _validate_webhook_url(webhook_url)
        except WebhookURLRejected as e:
            raise HTTPException(status_code=400, detail=str(e))
    file_data: List[Dict[str, Any]] = [
        {"filename": f.filename, "bytes": await _read_upload(f)} for f in files
    ]
    job_id = batch.new_job(total=len(file_data))

    async def _process_one(fd: Dict[str, Any]) -> Dict[str, Any]:
        out = await _extract_text_core(fd["bytes"], route, max_pages)
        return {"filename": fd["filename"], **out}

    background.add_task(batch.process, job_id, file_data, _process_one, webhook_url)
    return {"job_id": job_id, "total": len(file_data), "webhook_url": webhook_url}


@app.post("/extract", response_model=ProcessResponse)
async def extract(
    file: UploadFile = File(...),
    route: str = Form("vision_route_a"),
    doc_type: str = Form("invoice"),
) -> ProcessResponse:
    """
    Full extraction pipeline with 3 routes (multi-page PDFs handled end-to-end):
      - vision_route_a  (Claude Sonnet 4.6 Vision - Route A)
      - vision_route_b  (Ollama vision, local or self-hosted-remote - Route B)
      - ocr_fallback    (Tesseract OCR + LLM cleanup - Route C)

    Route B (set via ROUTE_B_MODE env var — never a third-party inference API):
      - local:  Ollama running on this same machine/container (OLLAMA_HOST)
      - remote: Ollama running on hardware you control elsewhere — same LAN or
                reachable over the internet (ROUTE_B_REMOTE_ENDPOINT)

    Vision models (OLLAMA_MODEL, any Ollama vision tag):
      - qwen2.5vl:7b (default) - lighter, works on most GPUs
      - llama3.2-vision:11b - better for complex layouts, needs CUDA >= 7.5

    Route B automatically falls back to Route C on any failure, with detailed logging.
    """
    t0 = time.time()
    data = await _read_upload(file)

    if workspace_logger:
        workspace_logger.log_request("/extract", {"route": route, "doc_type": doc_type})

    out = await _run_route(data, route, doc_type)

    if workspace_logger:
        workspace_logger.log_response("/extract", 200, (time.time() - t0) * 1000)

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
    route: str = Form("vision_route_a"),
    doc_type: str = Form("auto"),
) -> ProcessResponse:
    """
    One-shot pipeline: upload → (auto-classify) → multi-page extract → structured JSON.

    `doc_type="auto"` content-classifies the document first (text-based heuristic), then runs
    the chosen route. Tables are included for PDFs. Returns doc_type, fields, confidence,
    page_count.

    Routes:
      - vision_route_a: Claude Sonnet 4.6 Vision (high quality)
      - vision_route_b: Ollama vision, local or self-hosted-remote, auto-fallback to Route C
      - ocr_fallback: Route C (Tesseract OCR + LLM cleanup)
    """
    t0 = time.time()
    data = await _read_upload(file)

    from services.ocr_extractor import (
        DocumentClassifier, extract_text_from_image, extract_text_from_pdf,
        extract_text_native_office, is_pdf,
    )

    # raw_text has always been declared on ProcessResponse but was never populated —
    # every consumer wanting the document's actual prose (RAG ingesters especially) got
    # null and had to fall back to the typed `fields`, which for a long report is a
    # handful of characters. Populate it from the same text layer the OCR route uses.
    #
    # Extracted once, up front, and reused for both this and the doc_type="auto"
    # classifier sample below — this used to run OCR/text-layer extraction on the same
    # document twice per call (once for a 2-page classify sample, once again for the
    # full raw_text), which on a single-page image is the exact same Tesseract call
    # made back to back for no reason. One extraction is always <= the cost of two.
    #
    # PPTX/DOCX/XLSX get native extraction here too, for the same reason as
    # _extract_text_core: they're XML archives, not images — extract_text_from_image
    # would fail on them outright (PIL can't open a zip as a raster image).
    raw_text = None
    try:
        office_text = None if is_pdf(data) else extract_text_native_office(data)
        if office_text is not None:
            raw_text = office_text
        else:
            raw_text = extract_text_from_pdf(data, max_pages=settings.MAX_PDF_PAGES) if is_pdf(data) \
                else extract_text_from_image(data)
    except Exception:
        log.exception("raw_text extraction failed (non-fatal)")

    if doc_type == "auto":
        sample = (raw_text or "")[:4000]
        detected, _cls_conf = DocumentClassifier.classify_document(sample)
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
            log.exception("Unexpected error")
            pass

    return ProcessResponse(
        doc_type=doc_type,
        route=route,
        fields=fields,
        confidence=_confidence_of(fields),
        page_count=out["page_count"],
        processing_time_ms=round((time.time() - t0) * 1000, 1),
        raw_text=raw_text or None,
    )


@app.post("/extract-fields")
async def extract_fields(
    file: UploadFile = File(...),
    route: str = Form("vision_route_a"),
) -> Dict[str, Any]:
    """
    Generic form-field extraction: label -> value pairs, independent of the
    invoice/contract/receipt doc-type schemas used by /extract. Reuses the "form"
    prompt (handles checkboxes and handwritten entries on the vision routes).
    """
    t0 = time.time()
    data = await _read_upload(file)
    out = await _run_route(data, route, doc_type="form")
    fields = out["fields"] if isinstance(out["fields"], dict) else {}
    return {
        "route": route,
        "page_count": out["page_count"],
        "form_title": fields.get("form_title"),
        "fields": fields.get("fields"),
        "confidence": _confidence_of(fields),
        "processing_time_ms": round((time.time() - t0) * 1000, 1),
        "error": fields.get("error"),
        "raw": fields,
    }


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
        pdf_bytes = await _read_upload(file)
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
    webhook_url: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """
    Start a background batch process and return a job_id.

    If `webhook_url` is set, DocIntel POSTs the job summary + results to it once the
    batch completes — no polling needed. This is the integration point for n8n (or
    Zapier/Make/any HTTP-triggered automation): point webhook_url at an n8n Webhook
    node's URL. See docs/n8n/README.md for a worked example.
    """
    if webhook_url:
        try:
            _validate_webhook_url(webhook_url)
        except WebhookURLRejected as e:
            raise HTTPException(status_code=400, detail=str(e))
    file_data: List[Dict[str, Any]] = []
    for f in files:
        file_data.append({
            "filename": f.filename,
            "bytes": await _read_upload(f),
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

    background.add_task(batch.process, job_id, file_data, _process_one, webhook_url)
    return {"job_id": job_id, "total": len(file_data), "webhook_url": webhook_url}


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


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """Catch-all so direct navigation, refresh, or a bookmarked/shared link to
    any frontend route serves the SPA instead of a raw 404 -- React Router
    then resolves the route client-side. Declared last so every real API/WS
    route above still wins.

    Real static files in frontend/dist/ (favicon, logo, sw.js, ...) are
    served directly rather than falling back to index.html for them.
    """
    root = _os.path.dirname(__file__)
    dist = _os.path.realpath(_os.path.join(root, "frontend", "dist"))
    candidate = _os.path.realpath(_os.path.join(dist, full_path))
    if candidate.startswith(dist + _os.sep) and _os.path.isfile(candidate):
        return FileResponse(candidate)
    spa = _os.path.join(dist, "index.html")
    if _os.path.exists(spa):
        return FileResponse(spa)
    raise HTTPException(status_code=404, detail="Not Found")
