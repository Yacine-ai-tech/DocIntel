"""Key-field scoring for the DocIntel eval (pure functions, no LLM/IO — unit-testable)."""
from __future__ import annotations

import re
from typing import Any, Dict

KEY_FIELDS = ["vendor", "invoice_number", "date", "currency", "subtotal", "tax", "total"]
_NUMERIC = {"subtotal", "tax", "total"}


def norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s if s is not None else "").strip().lower())


def num(v: Any):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = re.sub(r"[^0-9.\-]", "", str(v))
    try:
        return round(float(s), 2) if s not in ("", "-", ".") else None
    except ValueError:
        return None


def score_fields(expected: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, bool]:
    """Per-key-field correctness: vendor lenient, ids/date/currency exact (normalized),
    numerics within max(0.02, 1%)."""
    actual = actual or {}
    f: Dict[str, bool] = {}
    ev, av = norm(expected.get("vendor")), norm(actual.get("vendor"))
    f["vendor"] = bool(ev and av and (ev == av or ev in av or av in ev))
    f["invoice_number"] = norm(expected.get("invoice_number")) == norm(actual.get("invoice_number"))
    f["date"] = norm(expected.get("date")) == norm(actual.get("date"))
    f["currency"] = norm(expected.get("currency")) == norm(actual.get("currency"))
    for k in _NUMERIC:
        en, an = num(expected.get(k)), num(actual.get(k))
        f[k] = en is not None and an is not None and abs(en - an) <= max(0.02, abs(en) * 0.01)
    return f
