"""SuryaExtractor smoke test — stub-safe (passes whether or not surya-ocr is installed)."""
import io

import pytest


def _png_bytes():
    Image = pytest.importorskip("PIL.Image")
    buf = io.BytesIO()
    Image.new("RGB", (200, 80), "white").save(buf, "PNG")
    return buf.getvalue()


def test_surya_extractor_imports_and_returns_dict():
    from services.surya_extractor import SuryaExtractor
    ex = SuryaExtractor(langs=["en"])
    out = ex.extract(_png_bytes())
    assert isinstance(out, dict)
    assert out.get("method") == "surya"
    # When surya isn't installed it must degrade to a stub, not raise.
    assert "text" in out and "lines" in out
