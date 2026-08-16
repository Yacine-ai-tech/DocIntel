"""Merge structured field dicts extracted from multiple chunks of one large document.

For 100+ page PDFs we can't send every page to a vision model in a single request (token
blow-up), so the pipeline processes the document in page-chunks ("map") and merges the
per-chunk field dicts here ("reduce"). Merge rules are doc-type-agnostic:

  - list fields (e.g. line_items)        -> concatenated across chunks, in page order
  - running-total fields (total, ...)     -> last non-empty wins (totals sit on later pages)
  - all other scalar fields (vendor, ...) -> first non-empty wins (headers sit on early pages)
  - _confidence                           -> the minimum across chunks (most conservative)
"""
from __future__ import annotations

from typing import Any, Dict, List

# Fields whose value typically appears on a *later* page and should override earlier nulls.
_LAST_WINS = {
    "total", "grand_total", "amount_due", "balance_due", "total_due",
    "net_income", "ebitda", "total_amount",
}


def _empty(v: Any) -> bool:
    return v is None or v == "" or v == [] or v == {}


def merge_doc_fields(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Reduce per-chunk extraction dicts into one. Drops chunks that errored; if all errored,
    returns an error dict carrying the first failure for debugging.

    When SOME chunks succeed and others fail, the merged result used to look
    identical to a fully successful merge — no error, no partial flag, nothing
    — silently missing whatever fields/line-items lived on the failed pages
    (e.g. a dropped chunk silently changes a computed subtotal with no signal
    anything went wrong). Now every result carries `_chunks_total`/
    `_chunks_failed`, and any failure — including the "only one chunk
    succeeded" case, which used to skip this signal entirely via an early
    return — sets `_partial: true` with a `_confidence` penalty, so callers/UI
    can surface "extraction may be incomplete" instead of presenting a
    silently wrong result as authoritative.
    """
    good = [c for c in chunks if isinstance(c, dict) and "error" not in c]
    n_total = len(chunks)
    n_failed = n_total - len(good)

    if not good:
        first = next((c for c in chunks if isinstance(c, dict)), {})
        return {"error": "all_chunks_failed", "detail": first.get("error", "unknown"),
                "_chunks_total": n_total, "_chunks_failed": n_failed}

    if len(good) == 1:
        merged = dict(good[0])
    else:
        merged = {}
        confidences: List[float] = []
        for c in good:
            for k, v in c.items():
                if k == "_confidence":
                    if isinstance(v, (int, float)):
                        confidences.append(float(v))
                    continue
                if k.startswith("_"):  # other private keys are set by the caller
                    continue
                if isinstance(v, list):
                    cur = merged.get(k)
                    merged[k] = (cur if isinstance(cur, list) else []) + v
                elif k in _LAST_WINS:
                    if not _empty(v):
                        merged[k] = v  # later chunk overrides → last non-empty wins
                else:
                    if _empty(merged.get(k)) and not _empty(v):
                        merged[k] = v  # first non-empty wins
        if confidences:
            merged["_confidence"] = round(min(confidences), 3)

    merged["_chunks_total"] = n_total
    merged["_chunks_failed"] = n_failed
    if n_failed:
        merged["_partial"] = True
        # Penalize confidence proportionally to how much of the document is missing,
        # rather than leaving whatever the successful chunks alone would have reported.
        penalty = 1.0 - (n_failed / n_total) * 0.5
        prior = merged.get("_confidence")
        merged["_confidence"] = round((prior if isinstance(prior, (int, float)) else 1.0) * penalty, 3)
    return merged
