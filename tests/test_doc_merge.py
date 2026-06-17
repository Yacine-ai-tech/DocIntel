"""Tests for the large-document chunk merge ("reduce" step of the 100+ page pipeline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.doc_merge import merge_doc_fields  # noqa: E402


def test_single_chunk_passthrough():
    assert merge_doc_fields([{"vendor": "Acme", "total": 10}]) == {"vendor": "Acme", "total": 10}


def test_first_non_empty_wins_for_headers():
    # vendor appears on page 1 (chunk 0); later chunks have null/empty → keep the first.
    merged = merge_doc_fields([
        {"vendor": "Acme", "invoice_number": None},
        {"vendor": None, "invoice_number": "INV-9"},
    ])
    assert merged["vendor"] == "Acme"
    assert merged["invoice_number"] == "INV-9"


def test_last_non_empty_wins_for_totals():
    # the grand total only appears on the last page → later chunk overrides.
    merged = merge_doc_fields([
        {"total": None, "subtotal": 100},
        {"total": 118.0},
    ])
    assert merged["total"] == 118.0
    assert merged["subtotal"] == 100


def test_list_fields_concatenate_in_order():
    merged = merge_doc_fields([
        {"line_items": [{"d": "a"}]},
        {"line_items": [{"d": "b"}, {"d": "c"}]},
    ])
    assert [i["d"] for i in merged["line_items"]] == ["a", "b", "c"]


def test_confidence_is_minimum():
    merged = merge_doc_fields([{"_confidence": 0.9, "x": 1}, {"_confidence": 0.6, "y": 2}])
    assert merged["_confidence"] == 0.6


def test_errored_chunks_dropped():
    merged = merge_doc_fields([{"error": "boom"}, {"vendor": "Acme", "total": 5}])
    assert merged["vendor"] == "Acme" and "error" not in merged


def test_all_errored_returns_error():
    merged = merge_doc_fields([{"error": "a"}, {"error": "b"}])
    assert merged["error"] == "all_chunks_failed"
