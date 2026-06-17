"""
Deterministic post-processing for extracted document fields.

STRATEGY §3.4 + Day 36-37 are explicit that LLMs are unreliable at locale-specific
*number*, *currency* and *date* normalization, and call for a hybrid layer: extract with the
LLM, then normalize these fields deterministically. This module is that layer. It is
multi-currency and multi-locale by design — not specialised to any one region:

- ``normalize_amount``   locale-aware money/number string -> float
                         (US "1,234.56", EU "1.234,56", spaced "1 234 567",
                          Swiss "1'234.56", parenthesised negatives) — never trusts a
                          single locale; the rightmost of '.'/',' is the decimal mark.
- ``normalize_currency`` symbol or code -> ISO 4217 ($/€/£/¥/₹/₦/₩/FCFA/RM/zł/…),
                         covering the STRATEGY-named USD/EUR/GBP/JPY plus ~40 more.
- ``normalize_date``     any locale's date -> ISO 8601 (YYYY-MM-DD) via ``dateparser``
                         (graceful fallback to a set of common formats when it is absent).
- ``normalize_fields``   applies the above to a doc-extraction dict by field name and
                         recurses into ``line_items`` / ``items``; infers a missing
                         ``currency`` from symbols seen in the amount strings.

The layer is conservative: if a value cannot be parsed it is left untouched, so it can only
*improve* the LLM's output, never lose information.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger(__name__)

try:
    import dateparser  # multi-locale date parsing (DD/MM/YYYY, "12 mars 2024", etc.)
    _DATEPARSER = True
except ImportError:  # pragma: no cover - optional dep
    _DATEPARSER = False
    log.warning("dateparser not installed — normalize_date falls back to common formats only")


# --------------------------------------------------------------------------- amounts

# Whitespace variants used as thousands grouping (incl. NBSP and narrow NBSP).
_SPACES = "    "


def normalize_amount(value: Any) -> Optional[float]:
    """Parse a money/number value from many locales into a float.

    Rules (locale-agnostic, no single-locale assumption):
      * Already numeric -> returned as float (the LLM's own parse is trusted).
      * Both '.' and ',' present -> the *rightmost* is the decimal mark, the other is
        thousands grouping ("1.234,56" -> 1234.56 ; "1,234.56" -> 1234.56).
      * One separator, repeated -> thousands grouping ("1.234.567" -> 1234567).
      * One separator, once, exactly 3 trailing digits -> thousands grouping
        ("1,234"/"1.234"/"12.000" -> 1234 / 12000) — the dominant invoice convention.
        (Trade-off: a genuine 3-decimal currency like KWD "1.234" reads as 1234; rare.)
      * One separator, once, !=3 trailing digits -> decimal mark ("12,34" -> 12.34).
      * Spaces / apostrophes are thousands grouping and stripped.
      * Parentheses or a leading '-' denote a negative amount.

    Returns None if nothing parseable remains.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None

    neg = s.lstrip().startswith("-") or (s.startswith("(") and s.rstrip().endswith(")"))
    # Drop everything that is not a digit or a grouping/decimal char.
    s = re.sub(r"[^\d.,'%s]" % re.escape(_SPACES), "", s)
    for sp in _SPACES + "'":
        s = s.replace(sp, "")
    if not s:
        return None

    has_dot, has_com = "." in s, "," in s
    if has_dot and has_com:
        if s.rfind(".") > s.rfind(","):      # 1,234.56  -> dot is decimal
            s = s.replace(",", "")
        else:                                 # 1.234,56  -> comma is decimal
            s = s.replace(".", "").replace(",", ".")
    elif has_com:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) != 3:   # 12,34 / 1234,5 / ,56 -> decimal
            s = s.replace(",", ".")
        else:                                          # 1,234 / 1,234,567   -> thousands
            s = s.replace(",", "")
    elif has_dot:
        parts = s.split(".")
        if len(parts) > 2:                             # 1.234.567 -> thousands
            s = s.replace(".", "")
        elif len(parts) == 2 and len(parts[1]) == 3:   # 1.234 / 12.000 -> thousands
            s = s.replace(".", "")
        # else: 1.5 / 12.34 / 1.2345 -> dot already the decimal mark

    try:
        f = float(s)
    except ValueError:
        return None
    return -f if neg else f


# --------------------------------------------------------------------------- currency

# ISO 4217 codes we recognise as-is (kept short; passthrough also uppercases any 3-letter code).
_ISO_CODES = {
    "USD", "EUR", "GBP", "JPY", "CNY", "INR", "CHF", "CAD", "AUD", "NZD", "HKD", "SGD",
    "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "RON", "RUB", "TRY", "ZAR", "BRL", "MXN",
    "ARS", "CLP", "COP", "AED", "SAR", "QAR", "KWD", "BHD", "ILS", "EGP", "MAD", "DZD",
    "TND", "NGN", "GHS", "KES", "UGX", "TZS", "XOF", "XAF", "KRW", "THB", "VND", "IDR",
    "MYR", "PHP", "PKR", "BDT", "LKR", "TWD",
}

# Word/symbol aliases -> ISO 4217. Order matters: longer, more specific keys win, so
# multi-char tokens ("FCFA", "RM", "US$") are matched before bare symbols ("$").
_CURRENCY_ALIASES = [
    ("FCFA", "XOF"), ("F.CFA", "XOF"), ("F CFA", "XOF"), ("CFA", "XOF"),
    ("US$", "USD"), ("U$S", "USD"), ("CA$", "CAD"), ("C$", "CAD"), ("A$", "AUD"),
    ("AU$", "AUD"), ("NZ$", "NZD"), ("HK$", "HKD"), ("S$", "SGD"), ("R$", "BRL"),
    ("RM", "MYR"), ("RP", "IDR"), ("RS.", "INR"), ("RS", "INR"), ("ZŁ", "PLN"),
    ("ZL", "PLN"), ("KČ", "CZK"), ("KC", "CZK"), ("RMB", "CNY"), ("CN¥", "CNY"),
    ("元", "CNY"), ("円", "JPY"), ("₩", "KRW"), ("₫", "VND"), ("฿", "THB"),
    ("₱", "PHP"), ("₦", "NGN"), ("₹", "INR"), ("₽", "RUB"), ("₪", "ILS"),
    ("₺", "TRY"), ("€", "EUR"), ("£", "GBP"), ("¥", "JPY"), ("$", "USD"),
]
# Match the LONGEST token first so multi-char tokens win over their substrings
# (e.g. "RMB" -> CNY beats "RM" -> MYR; "US$" -> USD beats "$" -> USD).
_CURRENCY_ALIASES.sort(key=lambda kv: -len(kv[0]))


def detect_currency_in_text(text: str) -> Optional[str]:
    """Return the ISO 4217 code for the first currency symbol/word found in ``text``."""
    if not text:
        return None
    up = str(text).upper()
    for token, iso in _CURRENCY_ALIASES:
        if token in up:
            return iso
    m = re.search(r"\b([A-Z]{3})\b", up)
    if m and m.group(1) in _ISO_CODES:
        return m.group(1)
    return None


def normalize_currency(value: Any) -> Optional[str]:
    """Map a currency symbol or name to an ISO 4217 code; passthrough valid 3-letter codes."""
    if not value:
        return None
    s = str(value).strip().upper()
    if s in _ISO_CODES:
        return s
    return detect_currency_in_text(s)


# --------------------------------------------------------------------------- dates

_DATE_FORMATS = (
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d",
    "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y", "%d/%m/%y", "%m/%d/%y",
)


def normalize_date(value: Any) -> Optional[str]:
    """Normalise a date from any locale to ISO 8601 (YYYY-MM-DD).

    Uses ``dateparser`` (handles DD/MM vs MM/DD, French/Spanish/German month names, etc.)
    with ``DD/MM`` preferred for ambiguous all-numeric dates (the world-majority order).
    Falls back to a list of common ``strptime`` formats when dateparser is unavailable.
    Returns the original string untouched if it cannot be parsed.
    """
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Already ISO YYYY-MM-DD.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    if _DATEPARSER:
        dt = dateparser.parse(s, settings={"DATE_ORDER": "DMY", "STRICT_PARSING": False})
        if dt:
            return dt.strftime("%Y-%m-%d")
    from datetime import datetime
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s  # leave unrecognised strings as-is rather than lose information


# --------------------------------------------------------------------------- field mapping

_AMOUNT_FIELDS = {
    "total", "subtotal", "tax", "amount", "unit_price", "price", "asking_price",
    "revenue", "cogs", "opex", "ebitda", "net_income", "balance", "balance_due",
    "amount_due", "amount_paid", "discount", "shipping", "grand_total", "quantity",
}
_CURRENCY_FIELDS = {"currency"}
_DATE_FIELDS = {
    "date", "invoice_date", "due_date", "effective_date", "expiration_date",
    "issue_date", "payment_date", "order_date",
}
_LIST_FIELDS = ("line_items", "items", "products")


def _apply(field: str, value: Any, seen_symbols: List[Optional[str]]) -> Any:
    key = field.lower()
    if key in _AMOUNT_FIELDS:
        if isinstance(value, str):
            seen_symbols.append(detect_currency_in_text(value))
        norm = normalize_amount(value)
        return norm if norm is not None else value
    if key in _CURRENCY_FIELDS:
        return normalize_currency(value) or value
    if key in _DATE_FIELDS:
        return normalize_date(value) or value
    return value


def normalize_fields(data: Dict[str, Any], doc_type: str = "default") -> Dict[str, Any]:
    """Normalise amount/currency/date fields in an extraction dict in place and return it.

    Recurses into list-of-dict fields (line_items / items). If ``currency`` is missing but a
    currency symbol appeared in an amount string (e.g. total was "$1,234.56"), it is inferred.
    Robust to non-dict input (returned unchanged).
    """
    if not isinstance(data, dict):
        return data
    seen_symbols: List[Optional[str]] = []

    for field, value in list(data.items()):
        if field in _LIST_FIELDS and isinstance(value, list):
            data[field] = [
                {k: _apply(k, v, seen_symbols) for k, v in row.items()} if isinstance(row, dict)
                else row
                for row in value
            ]
        else:
            data[field] = _apply(field, value, seen_symbols)

    # Infer a missing currency from symbols spotted in the amount strings.
    cur = data.get("currency")
    if not cur:
        for sym in seen_symbols:
            if sym:
                data["currency"] = sym
                break

    return data
