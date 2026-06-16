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


# Shared rules — the text may be concatenated from MULTIPLE pages (separated by form-feeds),
# so aggregate across them. Encode EU-decimal + ISO-currency normalization and confidence.
_RULES = (
    " The text may span multiple pages (separated by form-feed characters) — aggregate across "
    "them. Normalize numbers to a dot decimal (European '1.234,56' -> 1234.56; West African "
    "'1 234 567 FCFA' -> 1234567; strip thousands separators, spaces and currency symbols). "
    "Use ISO-4217 currency codes (the West African CFA franc 'FCFA'/'CFA'/'F CFA' is XOF, "
    "Central African is XAF) and ISO YYYY-MM-DD dates. "
    "Use null for missing fields. Include a numeric \"_confidence\" (0-1). Return ONLY valid JSON."
)

PROMPTS: Dict[str, str] = {
    "invoice": (
        "Extract structured invoice data as JSON. Fields: "
        "vendor, invoice_number, date, due_date, "
        "line_items: [{description, quantity, unit_price, total}], "
        "subtotal, tax, total, currency."
    ),
    "contract": (
        "Extract structured contract data as JSON. Fields: "
        "parties, effective_date, expiration_date, "
        "payment_terms, governing_law, term, key_clauses: [string]."
    ),
    "receipt": (
        "Extract structured receipt data as JSON. Fields: "
        "merchant, date, total, currency, tax, items: [{name, price, quantity}], "
        "payment_method."
    ),
    "financial_report": (
        "Extract structured financial-report data as JSON. Fields: "
        "period, revenue, cogs, opex, ebitda, net_income, key_metrics_summary."
    ),
    "auction_listing": (
        "Extract structured auction-listing data as JSON. Fields: "
        "item_title, category, condition (new|used|refurbished), "
        "asking_price, currency, location, image_url, key_specs: [{name, value}]."
    ),
    "form": (
        "Extract form data as JSON: form_title and a \"fields\" object mapping each label "
        "to its value (checkboxes as true/false)."
    ),
    "default": (
        "Extract any structured information from this document as JSON. "
        "Use field names that match the document's content."
    ),
}

# Max characters of OCR text to send (multi-page docs can be long; keep well within context).
_MAX_TEXT_CHARS = int(os.getenv("LLM_EXTRACT_MAX_CHARS", "24000"))


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
        if not text or not text.strip():
            return {"error": "empty_text", "doc_type": doc_type}

        prompt = PROMPTS.get(doc_type, PROMPTS["default"]) + _RULES
        content = ""
        for attempt in (1, 2):
            try:
                response = await acompletion(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": text[:_MAX_TEXT_CHARS]},
                    ],
                    temperature=0.1,
                )
                content = response.choices[0].message.content or "{}"
                return json.loads(_strip_fences(content))
            except json.JSONDecodeError as e:
                log.warning("LLM non-JSON (attempt %d): %s", attempt, e)
                if attempt == 1:
                    prompt += " Your previous reply was not valid JSON. Output ONLY the JSON object."
                    continue
                return {"error": "non_json_response", "raw": content[:500]}
            except Exception as e:
                log.exception("LLM extraction failed: %s", e)
                return {"error": str(e)}
        return {"error": "unreachable"}
