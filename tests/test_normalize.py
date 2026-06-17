"""
Deterministic tests for the multi-currency / multi-locale normalization layer
(services/normalize.py). No network, no LLM — these lock in the locale rules STRATEGY
§3.4 calls for (US/EU/spaced amounts, ISO 4217 currencies well beyond FCFA, ISO dates).
"""
import pytest

from services.normalize import (
    normalize_amount,
    normalize_currency,
    normalize_date,
    normalize_fields,
    detect_currency_in_text,
)


@pytest.mark.parametrize("raw,expected", [
    (1234.56, 1234.56),            # already numeric — trusted
    (1000, 1000.0),
    ("1,234.56", 1234.56),         # US
    ("$1,234.56", 1234.56),        # US with symbol
    ("1.234,56", 1234.56),         # EU
    ("1.234.567,89", 1234567.89),  # EU with multiple groupings
    ("1 234 567", 1234567.0),      # spaced (FR / West-Africa)
    ("1 234 567 FCFA", 1234567.0), # spaced + currency word
    ("1'234.56", 1234.56),         # Swiss apostrophe
    ("12,34", 12.34),              # bare EU decimal (2 trailing)
    ("1,234", 1234.0),             # bare thousands (3 trailing)
    ("12.000", 12000.0),           # IDR/EU thousands (3 trailing dot)
    ("1.5", 1.5),                  # plain decimal
    ("(123.45)", -123.45),         # parenthesised negative
    ("-99.50", -99.5),
    ("€ 2.500,00", 2500.0),
    ("", None),
    ("n/a", None),
    (None, None),
    (True, None),                  # bool is not an amount
])
def test_normalize_amount(raw, expected):
    assert normalize_amount(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("$", "USD"), ("US$", "USD"), ("USD", "USD"),
    ("€", "EUR"), ("eur", "EUR"),
    ("£", "GBP"), ("¥", "JPY"), ("₹", "INR"), ("Rs.", "INR"),
    ("₦", "NGN"), ("₩", "KRW"), ("฿", "THB"), ("₫", "VND"),
    ("FCFA", "XOF"), ("F CFA", "XOF"), ("CFA", "XOF"),
    ("RM", "MYR"), ("R$", "BRL"), ("CA$", "CAD"), ("A$", "AUD"),
    ("RMB", "CNY"), ("zł", "PLN"), ("CHF", "CHF"),
    ("", None), ("not-a-currency", None),
])
def test_normalize_currency(raw, expected):
    assert normalize_currency(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("2024-03-12", "2024-03-12"),       # already ISO
    ("12/03/2024", "2024-03-12"),       # DMY preferred
    ("12-03-2024", "2024-03-12"),
    ("12.03.2024", "2024-03-12"),       # German style
    ("12 March 2024", "2024-03-12"),
    ("March 12, 2024", "2024-03-12"),
    ("", None),
])
def test_normalize_date(raw, expected):
    assert normalize_date(raw) == expected


def test_normalize_date_french_when_dateparser_present():
    # dateparser handles localized month names; skip gracefully if it's not installed.
    pytest.importorskip("dateparser")
    assert normalize_date("12 mars 2024") == "2024-03-12"


def test_detect_currency_in_text():
    assert detect_currency_in_text("Total: $1,234.56") == "USD"
    assert detect_currency_in_text("Montant 1 234 567 FCFA") == "XOF"
    assert detect_currency_in_text("no currency here") is None


def test_normalize_fields_invoice_eu():
    doc = {
        "vendor": "ACME GmbH",
        "invoice_date": "12/03/2024",
        "subtotal": "1.234,56",
        "tax": "234,57",
        "total": "1.469,13",
        "currency": "€",
        "line_items": [
            {"description": "Widget", "quantity": "2", "unit_price": "617,28", "total": "1.234,56"},
        ],
    }
    out = normalize_fields(doc, "invoice")
    assert out["subtotal"] == 1234.56
    assert out["tax"] == 234.57
    assert out["total"] == 1469.13
    assert out["currency"] == "EUR"
    assert out["invoice_date"] == "2024-03-12"
    assert out["line_items"][0]["unit_price"] == 617.28
    assert out["line_items"][0]["total"] == 1234.56


def test_normalize_fields_infers_currency_from_symbol():
    # currency field missing, but the total carried a symbol -> infer it.
    doc = {"merchant": "Cafe", "total": "$12.50"}
    out = normalize_fields(doc, "receipt")
    assert out["total"] == 12.5
    assert out["currency"] == "USD"


def test_normalize_fields_preserves_unparseable():
    doc = {"total": "see attached", "currency": "weird"}
    out = normalize_fields(doc, "invoice")
    assert out["total"] == "see attached"   # left untouched, not lost
    assert out["currency"] == "weird"


def test_normalize_fields_is_noop_on_non_dict():
    assert normalize_fields([1, 2, 3]) == [1, 2, 3]
