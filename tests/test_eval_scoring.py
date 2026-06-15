"""Unit tests for the eval key-field scorer (pure, no LLM/IO)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

from scoring import KEY_FIELDS, num, score_fields  # noqa: E402


def test_num_parses_currency_strings():
    assert num("$1,234.50") == 1234.50
    assert num("€9.99") == 9.99
    assert num(42) == 42.0
    assert num(None) is None
    assert num("n/a") is None


def test_perfect_match_all_fields():
    exp = {"vendor": "Acme Industrial Supply", "invoice_number": "INV-2026-5506",
           "date": "2026-05-06", "currency": "USD", "subtotal": 8076.56, "tax": 403.83, "total": 8480.39}
    got = dict(exp)
    f = score_fields(exp, got)
    assert all(f[k] for k in KEY_FIELDS)


def test_lenient_vendor_and_numeric_tolerance_and_currency_symbols():
    exp = {"vendor": "Acme Industrial Supply", "invoice_number": "INV-1", "date": "2026-01-01",
           "currency": "USD", "subtotal": 100.0, "tax": 8.0, "total": 108.0}
    actual = {"vendor": "ACME Industrial Supply Inc.",  # superset → lenient match
              "invoice_number": "inv-1", "date": "2026-01-01", "currency": "usd",
              "subtotal": "$100.00", "tax": 8.0, "total": 108.004}  # within tolerance
    f = score_fields(exp, actual)
    assert all(f[k] for k in KEY_FIELDS)


def test_detects_wrong_values():
    exp = {"vendor": "Acme", "invoice_number": "INV-1", "date": "2026-01-01",
           "currency": "USD", "subtotal": 100.0, "tax": 8.0, "total": 108.0}
    actual = {"vendor": "Globex", "invoice_number": "INV-2", "date": "2025-01-01",
              "currency": "EUR", "subtotal": 200.0, "tax": 8.0, "total": 250.0}
    f = score_fields(exp, actual)
    assert not f["vendor"] and not f["invoice_number"] and not f["date"]
    assert not f["currency"] and not f["subtotal"] and not f["total"]
    assert f["tax"]  # the one matching field


def test_missing_actual_fields_are_false():
    exp = {"vendor": "Acme", "total": 108.0}
    f = score_fields(exp, {})
    assert not f["vendor"] and not f["total"]
