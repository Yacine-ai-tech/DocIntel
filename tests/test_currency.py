"""Currency normalization tests — focus on the West-African CFA franc (FCFA → XOF)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

from run_benchmark import _cur  # noqa: E402


def test_fcfa_variants_map_to_xof():
    for s in ("FCFA", "fcfa", "CFA", "F CFA", "XOF", "xof", "FCFA XOF"):
        assert _cur(s) == "XOF", s


def test_central_african_cfa_is_xaf():
    assert _cur("XAF") == "XAF"


def test_common_currencies_still_normalize():
    assert _cur("$") == "USD"
    assert _cur("€") == "EUR"
    assert _cur("₹") == "INR"
    assert _cur("usd") == "USD"


def test_unknown_three_letter_passthrough_uppercased():
    assert _cur("jpy") == "JPY"
