"""
Vision-LLM document extractor — 2026 vision-first route.

Routes:
  - Premium: Claude Sonnet 4.6 Vision via LiteLLM
  - Local: Ollama Llama 3.2 Vision via LiteLLM (local privacy)
"""
from __future__ import annotations

import base64
import json
import os
import re
from typing import Any, Dict, Optional

from core.logger import get_logger

log = get_logger(__name__)

try:
    from litellm import acompletion
    _LITELLM = True
except ImportError:
    _LITELLM = False


VISION_PROMPTS: Dict[str, str] = {
    "invoice": (
        "You are a document understanding model. From the image, return a JSON "
        "with: vendor, invoice_number, date (YYYY-MM-DD), due_date (YYYY-MM-DD), "
        "line_items: [{description, quantity, unit_price, total}], "
        "subtotal, tax, total, currency. JSON only."
    ),
    "contract": (
        "From the contract image, return JSON: parties, effective_date, "
        "expiration_date, payment_terms, jurisdiction, key_clauses. JSON only."
    ),
    "receipt": (
        "From the receipt image, return JSON: merchant, date, total, currency, "
        "items: [{name, price}], payment_method. JSON only."
    ),
    "financial_report": (
        "From the financial-report image, return JSON: period, revenue, cogs, "
        "opex, ebitda, net_income, key_metrics_summary. JSON only."
    ),
    "auction_listing": (
        "From this auction-listing image, return JSON: item_title, category, "
        "condition, asking_price, currency, location, key_specs. JSON only."
    ),
    "default": (
        "Describe the document and extract any structured data as JSON. "
        "Return JSON only."
    ),
}


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def extract_via_vision_llm(
    image_bytes: bytes,
    model: Optional[str] = None,
    doc_type: str = "invoice",
) -> Dict[str, Any]:
    """
    Extract structured data from a document image using a vision-capable LLM.

    Args:
        image_bytes: Raw PNG/JPEG bytes.
        model: LiteLLM vision-capable model. Defaults to LLM_VISION_PREMIUM.
        doc_type: One of invoice|contract|receipt|financial_report|auction_listing|default.

    Returns:
        A dict of extracted fields. Empty/error dict if extraction fails.
    """
    if not _LITELLM:
        return {"error": "litellm_not_installed"}

    model = model or os.getenv("LLM_VISION_PREMIUM", "anthropic/claude-sonnet-4-6")
    b64 = base64.b64encode(image_bytes).decode()
    prompt = VISION_PROMPTS.get(doc_type, VISION_PROMPTS["default"])

    try:
        response = await acompletion(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }],
            temperature=0.1,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(_strip_fences(content))
    except json.JSONDecodeError as e:
        log.warning("Vision-LLM returned non-JSON: %s", e)
        return {"error": "non_json_response", "raw": content[:500]}
    except Exception as e:
        log.exception("Vision extraction failed: %s", e)
        return {"error": str(e)}


async def classify_image(
    image_bytes: bytes,
    categories: list[str],
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Vision-first object classification — used for auction-listing aggregation.

    Args:
        image_bytes: Raw image bytes.
        categories: A list of candidate categories (e.g. ["tractor", "lathe", "crane"]).
        model: LiteLLM vision-capable model.

    Returns:
        {"category": str, "confidence": float in [0,1], "reasoning": str}
    """
    if not _LITELLM:
        return {"error": "litellm_not_installed"}

    model = model or os.getenv("LLM_VISION_PREMIUM", "anthropic/claude-sonnet-4-6")
    b64 = base64.b64encode(image_bytes).decode()
    prompt = (
        f"Classify the object in this image into one of: {', '.join(categories)}. "
        "Return JSON: {category, confidence (0-1), reasoning}. JSON only."
    )

    try:
        response = await acompletion(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }],
            temperature=0.1,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(_strip_fences(content))
    except Exception as e:
        log.exception("classify_image failed: %s", e)
        return {"category": "unknown", "confidence": 0.0, "error": str(e)}
