"""
Vision-LLM document extractor — 2026 vision-first route.

Routes:
  - Premium: Claude Sonnet 4.6 Vision via LiteLLM (complex layouts, handwriting, mixed langs)
  - Local: Ollama Llama 3.2 Vision via LiteLLM (local privacy)

Multi-page documents are supported: pass a list of page images and they are sent to the
vision model in one request so it can aggregate across pages (totals on a later page,
multi-page contracts, etc.).
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
from typing import Any, Dict, List, Optional, Union

from core.logger import get_logger

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

# Cap how many page-images are sent to the vision model in one request (cost/safety).
MAX_VISION_IMAGES = int(os.getenv("MAX_VISION_IMAGES", "20"))
# Downscale page images whose longest side exceeds this (px) to control token cost.
VISION_MAX_EDGE = int(os.getenv("VISION_MAX_EDGE", "2200"))

# Rules appended to every doc-type prompt. They encode the hard-won extraction lessons:
# multi-page aggregation, handwriting, EU decimals, ISO currency, nulls, self-reported
# confidence. Keep terse — vision models follow compact instructions well.
_RULES = (
    " The document may span MULTIPLE page images — read ALL of them and aggregate "
    "(a field such as the grand total may appear only on a later page; line items may "
    "continue across pages). Transcribe handwritten values too. Normalize every number to "
    "a machine-readable decimal with a dot (e.g. European '1.234,56' -> 1234.56; West "
    "African '1 234 567 FCFA' -> 1234567; strip thousands separators, spaces and currency "
    "symbols). Use ISO-4217 currency codes (USD, EUR, GBP, INR, JPY, XOF, XAF, ...); the "
    "West African CFA franc written 'FCFA'/'CFA'/'F CFA' is XOF (Central African CFA is "
    "XAF). Dates as ISO YYYY-MM-DD. If a field is not present, use null. "
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


async def _vision_call(model: str, prompt: str, imgs: List[bytes]) -> str:
    content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
    content.extend(_image_block(i) for i in imgs)
    response = await acompletion(
        model=model,
        messages=[{"role": "user", "content": content}],
        temperature=0.1,
    )
    return response.choices[0].message.content or "{}"


async def extract_via_vision_llm(
    images: Union[bytes, List[bytes]],
    model: Optional[str] = None,
    doc_type: str = "invoice",
) -> Dict[str, Any]:
    """
    Extract structured data from one or more document page images using a vision LLM.

    Args:
        images: Raw PNG/JPEG bytes, or a list of page images for a multi-page document.
        model: LiteLLM vision-capable model. Defaults to LLM_VISION_PREMIUM.
        doc_type: invoice|contract|receipt|financial_report|auction_listing|form|default.

    Returns:
        A dict of extracted fields (with a "_confidence" float and "_pages" count).
        Error dict if extraction fails.
    """
    if not _LITELLM:
        return {"error": "litellm_not_installed"}

    imgs = _coerce_images(images)
    if not imgs:
        return {"error": "no_image"}
    n_pages = len(imgs)
    if n_pages > MAX_VISION_IMAGES:
        log.warning("document has %d pages — capping vision input at %d", n_pages, MAX_VISION_IMAGES)
        imgs = imgs[:MAX_VISION_IMAGES]

    model = model or os.getenv("LLM_VISION_PREMIUM", "anthropic/claude-sonnet-4-6")
    prompt = VISION_PROMPTS.get(doc_type, VISION_PROMPTS["default"]) + _RULES

    content = ""
    for attempt in (1, 2):
        try:
            content = await _vision_call(model, prompt, imgs)
            result = json.loads(_strip_fences(content))
            if isinstance(result, dict):
                result.setdefault("_confidence", None)
                result["_pages"] = n_pages
            return result
        except json.JSONDecodeError as e:
            log.warning("Vision-LLM non-JSON (attempt %d): %s", attempt, e)
            if attempt == 1:
                prompt += " Your previous reply was not valid JSON. Output ONLY the JSON object."
                continue
            return {"error": "non_json_response", "raw": content[:500], "_pages": n_pages}
        except Exception as e:
            log.exception("Vision extraction failed: %s", e)
            return {"error": str(e), "_pages": n_pages}
    return {"error": "unreachable"}


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

    model = model or os.getenv("LLM_VISION_PREMIUM", "anthropic/claude-sonnet-4-6")
    prompt = (
        f"Classify the main object/document in this image into one of: {', '.join(categories)}. "
        "Return ONLY JSON: {category, confidence (0-1), reasoning}."
    )
    try:
        content = await _vision_call(model, prompt, [image_bytes])
        return json.loads(_strip_fences(content))
    except Exception as e:
        log.exception("classify_image failed: %s", e)
        return {"category": "unknown", "confidence": 0.0, "error": str(e)}
