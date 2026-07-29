"""
Vision-LLM document extractor — DocIntel 2.0

Routes:
  - Route A: Claude Sonnet 4.6 Vision via LiteLLM (premium quality, complex layouts)
  - Route B: Ollama vision model (local GPU or remote Ollama-compatible endpoint)
             Model selection: OLLAMA_MODEL (default: qwen2.5vl:7b)
             Mode selection:  ROUTE_B_MODE (local | remote)
             See services/route_b.py for full configuration reference.
  - Route C: OCR fallback (Tesseract + LLM cleanup) — automatic fallback for Route B failures

Supported Ollama vision models (primary focus per strategy.md):
  - Qwen 2.5-VL 7B / 72B  — lighter, works on most GPUs, great for forms/invoices
  - Llama 3.2 Vision 11B / 90B — better for complex mixed-language layouts
  Any other Ollama vision model (minicpm-v, llava, etc.) also works via OLLAMA_MODEL.

Multi-page documents:
  Both Route A and Route B support arbitrarily large PDFs via chunked map-reduce.
  Route B uses VISION_PAGES_PER_CALL_LOCAL (default 2) pages per chunk and
  ROUTE_B_CHUNK_CONCURRENCY (default 1, sequential) to avoid GPU OOM.

Extracted numeric/currency/date fields are normalized deterministically by
`services.normalize` after extraction — LLMs are unreliable at locale parsing.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
from typing import Any, Dict, List, Optional, Union

from core.logger import get_logger
from services.doc_merge import merge_doc_fields
from services.normalize import normalize_fields

log = get_logger(__name__)

try:
    from litellm import acompletion
    _LITELLM = True
except ImportError:
    _LITELLM = False

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

# ─── Page/chunk limits ────────────────────────────────────────────────────────
# Pages sent to the vision model in ONE request. Larger docs are split into
# chunks and merged (map-reduce) so 100+ page PDFs work without a token blow-up.
VISION_PAGES_PER_CALL = int(os.getenv("VISION_PAGES_PER_CALL", "8"))
# Route B (Ollama) uses smaller context windows — fewer pages per chunk.
VISION_PAGES_PER_CALL_LOCAL = int(os.getenv("VISION_PAGES_PER_CALL_LOCAL", "2"))
# Hard ceiling on total pages per document (cost/safety). Raise via env for huge docs.
MAX_VISION_PAGES = int(os.getenv("MAX_VISION_PAGES", "200"))
# Concurrent Route A vision calls when chunking. Route B uses ROUTE_B_CHUNK_CONCURRENCY.
VISION_CHUNK_CONCURRENCY = int(os.getenv("VISION_CHUNK_CONCURRENCY", "3"))
# Downscale page images whose longest side exceeds this (px) to control token cost.
VISION_MAX_EDGE = int(os.getenv("VISION_MAX_EDGE", "2200"))


# ─── Extraction prompts ───────────────────────────────────────────────────────
# Rules appended to every prompt — encode hard-won extraction lessons.
_RULES = (
    " The document may span MULTIPLE page images — read ALL of them and aggregate "
    "(a field such as the grand total may appear only on a later page; line items may "
    "continue across pages). Transcribe handwritten values too. Normalize every number to "
    "a machine-readable decimal with a dot (US '1,234.56' -> 1234.56; European '1.234,56' "
    "-> 1234.56; spaced '1 234 567 FCFA' -> 1234567; strip thousands separators, spaces and "
    "currency symbols). Use ISO-4217 currency codes (USD, EUR, GBP, JPY, INR, CNY, XOF, XAF, "
    "...); the West African CFA franc written 'FCFA'/'CFA'/'F CFA' is XOF (Central African "
    "CFA is XAF). Dates as ISO YYYY-MM-DD. If a field is not present, use null. "
    "Also include a numeric \"_confidence\" between 0 and 1 for the overall extraction. "
    "Return ONLY a single valid JSON object, no prose, no markdown fences."
)

VISION_PROMPTS: Dict[str, str] = {
    "invoice": (
        "You are a precise invoice data extractor. Return JSON with: vendor, invoice_number, "
        "date, due_date, line_items: [{description, quantity, unit_price, total}], subtotal, "
        "tax, total, currency."
    ),
    "contract": (
        "You are a contract analyst. Return JSON with: parties, effective_date, "
        "expiration_date, payment_terms, governing_law, term, key_clauses: [string], "
        "signatures: [{name, role}]."
    ),
    "receipt": (
        "You are a receipt data extractor. Return JSON with: merchant, date, total, currency, "
        "tax, items: [{name, price, quantity}], payment_method."
    ),
    "financial_report": (
        "You are a financial-report extractor. Return JSON with: period, revenue, cogs, opex, "
        "ebitda, net_income, key_metrics_summary."
    ),
    "auction_listing": (
        "You are an auction-listing extractor. Return JSON with: item_title, category, "
        "condition, asking_price, currency, location, key_specs."
    ),
    "form": (
        "You are a form-field extractor. Return JSON with: form_title and a \"fields\" object "
        "mapping each label to its filled value (including handwritten entries; checkboxes as "
        "true/false)."
    ),
    "default": (
        "Extract all structured data from the document. Use field names that match its content."
    ),
}


# ─── Utility helpers ──────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _coerce_images(images: Union[bytes, List[bytes]]) -> List[bytes]:
    if isinstance(images, (bytes, bytearray)):
        return [bytes(images)]
    return [bytes(i) for i in images if i]


def _downscale(image_bytes: bytes) -> bytes:
    """Shrink oversized page images to keep vision token cost bounded. No-op without PIL."""
    if not _PIL:
        return image_bytes
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if max(img.size) <= VISION_MAX_EDGE:
            return image_bytes
        ratio = VISION_MAX_EDGE / max(img.size)
        img = img.convert("RGB").resize((int(img.width * ratio), int(img.height * ratio)))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()
    except Exception as e:
        log.warning("image downscale failed (%s) — sending original", e)
        return image_bytes


def _image_block(image_bytes: bytes) -> Dict[str, Any]:
    b64 = base64.b64encode(_downscale(image_bytes)).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}


# ─── Route A: Claude Sonnet 4.6 Vision ───────────────────────────────────────

async def _vision_call_route_a(model: str, prompt: str, imgs: List[bytes]) -> str:
    """Route A: Claude Sonnet 4.6 Vision via LiteLLM (high quality, no fallback needed)."""
    log.info("Route A: using %s", model)
    if not _LITELLM:
        raise RuntimeError("Route A requires litellm — install it with: pip install litellm")
    content = [{"type": "text", "text": prompt}]
    for img in imgs:
        content.append(_image_block(img))
    response = await acompletion(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=2048,
        temperature=0.1,
    )
    return response.choices[0].message.content


async def _extract_one_route_a(model: str, prompt: str, imgs: List[bytes]) -> Dict[str, Any]:
    """One Route A vision call over up to VISION_PAGES_PER_CALL images, with JSON retry."""
    p, last = prompt, ""
    for attempt in (1, 2):
        try:
            last = await _vision_call_route_a(model, p, imgs)
            result = json.loads(_strip_fences(last))
            return result if isinstance(result, dict) else {"value": result}
        except json.JSONDecodeError as e:
            log.warning("Route A non-JSON (attempt %d): %s", attempt, e)
            if attempt == 1:
                p = prompt + " Your previous reply was not valid JSON. Output ONLY the JSON object."
                continue
            return {"error": "non_json_response", "raw": last[:500]}
        except Exception as e:
            log.exception("Route A extraction failed: %s", e)
            return {"error": str(e)}
    return {"error": "unreachable"}


# ─── Route B: Ollama Vision ───────────────────────────────────────────────────

async def _vision_call_route_b(prompt: str, imgs: List[bytes]) -> str:
    """
    Route B: Ollama vision call via services.route_b.call_route_b().
    Raises on failure — caller handles fallback to Route C.
    """
    from services.route_b import call_route_b
    mode = os.getenv("ROUTE_B_MODE", "local")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5vl:7b")
    log.info("Route B: mode=%s model=%s pages=%d", mode, model, len(imgs))
    return await call_route_b(prompt, imgs)


async def _extract_one_route_b(prompt: str, imgs: List[bytes]) -> Dict[str, Any]:
    """
    One Route B vision call with a single JSON-parse retry.
    Returns a parsed dict or an {"error": ...} dict. Never raises.
    """
    p, last = prompt, ""
    for attempt in (1, 2):
        try:
            last = await _vision_call_route_b(p, imgs)
            result = json.loads(_strip_fences(last))
            return result if isinstance(result, dict) else {"value": result}
        except json.JSONDecodeError as e:
            log.warning("Route B non-JSON (attempt %d): %s", attempt, e)
            if attempt == 1:
                p = prompt + " Your previous reply was not valid JSON. Output ONLY the JSON object."
                continue
            return {"error": "non_json_response", "raw": last[:500]}
        except Exception as e:
            log.error("Route B extraction failed: %s", e)
            return {"error": str(e), "_route_b_failed": True}
    return {"error": "unreachable"}


# ─── Public extraction entry point ────────────────────────────────────────────

async def extract_via_vision_llm(
    images: Union[bytes, List[bytes]],
    model: Optional[str] = None,
    doc_type: str = "invoice",
    route_b: bool = False,
) -> Dict[str, Any]:
    """
    Extract structured data from one or more document page images using a vision LLM.

    Multi-page documents are processed in page-chunks and merged (map-reduce), so
    100+ page PDFs work without exceeding token budgets.

    Args:
        images:  Raw PNG/JPEG bytes, or a list of page images for a multi-page document.
        model:   LiteLLM model string for Route A. Ignored for Route B (uses OLLAMA_MODEL).
        doc_type: invoice|contract|receipt|financial_report|auction_listing|form|default.
        route_b: If True, use Route B (Ollama) instead of Route A (Claude).

    Returns:
        A dict of extracted fields. Includes _confidence, _pages, _chunks (when chunked).
        Error dict if extraction fails completely.
    """
    imgs = _coerce_images(images)
    if not imgs:
        return {"error": "no_image"}
    n_pages = len(imgs)
    if n_pages > MAX_VISION_PAGES:
        log.warning("document has %d pages — capping at %d", n_pages, MAX_VISION_PAGES)
        imgs = imgs[:MAX_VISION_PAGES]
        n_pages = MAX_VISION_PAGES

    prompt = VISION_PROMPTS.get(doc_type, VISION_PROMPTS["default"]) + _RULES

    # ── Route B: Ollama vision ─────────────────────────────────────────────
    if route_b:
        per_call = VISION_PAGES_PER_CALL_LOCAL
        concurrency = int(os.getenv("ROUTE_B_CHUNK_CONCURRENCY", "1"))

        # Small document → single call
        if n_pages <= per_call:
            result = await _extract_one_route_b(prompt, imgs)
            if isinstance(result, dict) and "_route_b_failed" not in result:
                normalize_fields(result, doc_type)
                result.setdefault("_confidence", result.pop("_confidence", None))
                result["_pages"] = n_pages
                result.setdefault("_route_b_mode", os.getenv("ROUTE_B_MODE", "local"))
                result.setdefault("_route_b_model", os.getenv("OLLAMA_MODEL", "qwen2.5vl:7b"))
            return result

        # Large document → chunked map-reduce
        chunks = [imgs[i:i + per_call] for i in range(0, n_pages, per_call)]
        log.info(
            "Route B large document: %d pages → %d chunks of %d (concurrency=%d)",
            n_pages, len(chunks), per_call, concurrency,
        )
        sem = asyncio.Semaphore(concurrency)

        async def _run_b(chunk: List[bytes]) -> Dict[str, Any]:
            async with sem:
                return await _extract_one_route_b(prompt, chunk)

        parts = await asyncio.gather(*(_run_b(c) for c in chunks))

        # If any chunk failed, propagate the failure so Route C can take over
        failures = [p for p in parts if isinstance(p, dict) and p.get("_route_b_failed")]
        if failures:
            log.warning("Route B: %d/%d chunks failed — propagating failure for Route C fallback", len(failures), len(chunks))
            return {"error": str(failures[0].get("error", "chunk_failed")), "_route_b_failed": True}

        merged = merge_doc_fields([p for p in parts if isinstance(p, dict)])
        normalize_fields(merged, doc_type)
        merged.setdefault("_confidence", None)
        merged["_pages"] = n_pages
        merged["_chunks"] = len(chunks)
        merged["_route_b_mode"] = os.getenv("ROUTE_B_MODE", "local")
        merged["_route_b_model"] = os.getenv("OLLAMA_MODEL", "qwen2.5vl:7b")
        return merged

    # ── Route A: Claude Sonnet 4.6 Vision ─────────────────────────────────
    if not _LITELLM:
        return {"error": "litellm_not_installed — Route A requires litellm"}

    model = model or os.getenv("LLM_VISION_ROUTE_A", "anthropic/claude-sonnet-4-6")
    per_call = VISION_PAGES_PER_CALL

    # Small document → single call
    if n_pages <= per_call:
        result = await _extract_one_route_a(model, prompt, imgs)
        if isinstance(result, dict) and "error" not in result:
            normalize_fields(result, doc_type)
            result.setdefault("_confidence", None)
            result["_pages"] = n_pages
        return result

    # Large document → map-reduce over page chunks (bounded concurrency), then merge.
    chunks = [imgs[i:i + per_call] for i in range(0, n_pages, per_call)]
    log.info("Route A large document: %d pages → %d chunks of %d", n_pages, len(chunks), per_call)
    sem = asyncio.Semaphore(VISION_CHUNK_CONCURRENCY)

    async def _run_a(chunk: List[bytes]) -> Dict[str, Any]:
        async with sem:
            return await _extract_one_route_a(model, prompt, chunk)

    parts = await asyncio.gather(*(_run_a(c) for c in chunks))
    merged = merge_doc_fields([p for p in parts if isinstance(p, dict)])
    normalize_fields(merged, doc_type)
    merged.setdefault("_confidence", None)
    merged["_pages"] = n_pages
    merged["_chunks"] = len(chunks)
    return merged


# ─── Image classification (Route A only) ─────────────────────────────────────

async def classify_image(
    image_bytes: bytes,
    categories: List[str],
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Vision-first object classification — used for auction-listing aggregation.
    Returns {"category": str, "confidence": float in [0,1], "reasoning": str}.
    """
    if not _LITELLM:
        return {"error": "litellm_not_installed"}
    model = model or os.getenv("LLM_VISION_ROUTE_A", "anthropic/claude-sonnet-4-6")
    prompt = (
        f"Classify the main object/document in this image into one of: {', '.join(categories)}. "
        "Return ONLY JSON: {category, confidence (0-1), reasoning}."
    )
    try:
        content = await _vision_call_route_a(model, prompt, [image_bytes])
        return json.loads(_strip_fences(content))
    except Exception as e:
        log.exception("classify_image failed: %s", e)
        return {"category": "unknown", "confidence": 0.0, "error": str(e)}
