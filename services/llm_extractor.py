"""
LLMExtractor — Document text → structured JSON via LiteLLM (multi-provider).

Supports OCR-fallback route: text (post-OCR) is passed to an LLM for structured
extraction. Doc-type-specific prompts return JSON.
"""
from __future__ import annotations

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
    log.warning("litellm not installed — LLMExtractor will return stubs")


PROMPTS: Dict[str, str] = {
    "invoice": (
        "Extract structured invoice data as JSON. Fields: "
        "vendor, invoice_number, date (ISO YYYY-MM-DD), due_date (ISO), "
        "line_items: [{description, quantity, unit_price, total}], "
        "subtotal, tax, total, currency. Return ONLY valid JSON."
    ),
    "contract": (
        "Extract structured contract data as JSON. Fields: "
        "parties, effective_date (ISO), expiration_date (ISO), "
        "payment_terms, jurisdiction, key_clauses: [string]. JSON only."
    ),
    "receipt": (
        "Extract structured receipt data as JSON. Fields: "
        "merchant, date (ISO), total, currency, items: [{name, price}], "
        "payment_method. JSON only."
    ),
    "financial_report": (
        "Extract structured financial-report data as JSON. Fields: "
        "period, revenue, cogs, opex, ebitda, net_income, "
        "key_metrics_summary. JSON only."
    ),
    "auction_listing": (
        "Extract structured auction-listing data as JSON. Fields: "
        "item_title, category, condition (new|used|refurbished), "
        "asking_price, currency, location, image_url, "
        "key_specs: [{name, value}]. JSON only."
    ),
    "default": (
        "Extract any structured information from this document as JSON. "
        "Use field names that match the document's content. JSON only."
    ),
}


def _strip_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) from LLM output."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


class LLMExtractor:
    """Extract structured data from raw text using LiteLLM."""

    def __init__(self, model: Optional[str] = None):
        """
        Args:
            model: LiteLLM model string. Defaults to LLM_REASONING env var.
        """
        self.model = model or os.getenv("LLM_REASONING", "anthropic/claude-sonnet-4-6")

    async def extract(self, text: str, doc_type: str = "default") -> Dict[str, Any]:
        """
        Extract structured fields from text.

        Args:
            text: Raw OCR/PDF text from the document.
            doc_type: One of invoice|contract|receipt|financial_report|auction_listing|default.

        Returns:
            A dict of extracted fields. Empty dict if extraction fails.
        """
        if not _LITELLM:
            return {"error": "litellm_not_installed", "doc_type": doc_type}

        prompt = PROMPTS.get(doc_type, PROMPTS["default"])
        try:
            response = await acompletion(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text[:8000]},
                ],
                temperature=0.1,
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(_strip_fences(content))
        except json.JSONDecodeError as e:
            log.warning("LLM returned non-JSON: %s", e)
            return {"error": "non_json_response", "raw": content[:500]}
        except Exception as e:
            log.exception("LLM extraction failed: %s", e)
            return {"error": str(e)}
