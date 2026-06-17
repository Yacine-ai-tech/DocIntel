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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    app.mount("/demo", StaticFiles(directory="demo", html=True), name="demo")
except RuntimeError:
    log.warning("demo/ directory not found — /demo will not be served")

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
        if pdf:
            images = pdf_to_pngs(data, max_pages=settings.MAX_PDF_PAGES)
            if not images:
                return {"fields": {"error": "pdf_render_failed (install poppler/pdf2image)"},
                        "page_count": page_count}
        else:
            images = [data]
        fields = await extract_via_vision_llm(images, model=model, doc_type=doc_type)
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

@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "docintel", "version": "0.1.0"}


@app.post("/classify", response_model=ProcessResponse)
async def classify(file: UploadFile = File(...)) -> ProcessResponse:
    """Fast doc-type classification (filename-based heuristic + extension)."""
    name = (file.filename or "").lower()
    if any(k in name for k in ("invoice", "inv")):
        doc_type, confidence = "invoice", 0.85
    elif any(k in name for k in ("contract", "agreement")):
        doc_type, confidence = "contract", 0.8
    elif any(k in name for k in ("receipt",)):
        doc_type, confidence = "receipt", 0.8
    elif any(k in name for k in ("report", "statement")):
        doc_type, confidence = "financial_report", 0.7
    else:
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
