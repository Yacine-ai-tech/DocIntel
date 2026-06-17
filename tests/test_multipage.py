"""Unit tests for the multi-page PDF handling and vision/LLM helpers.

The pure-function tests always run. The PDF-render tests skip gracefully when poppler
(pdf2image) is not installed, so CI without the system binary stays green.
"""
import io

import pytest


def _make_pdf(n_pages: int = 2) -> bytes:
    """Build a valid n-page PDF in memory from blank PIL images (no text layer)."""
    Image = pytest.importorskip("PIL.Image")
    pages = [Image.new("RGB", (600, 800), "white") for _ in range(n_pages)]
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", save_all=True, append_images=pages[1:])
    return buf.getvalue()


# ── pure functions (no external binaries) ───────────────────────────────────────

def test_is_pdf_detects_magic():
    from services.ocr_extractor import is_pdf
    assert is_pdf(_make_pdf(1)) is True
    assert is_pdf(b"\x89PNG\r\n\x1a\n") is False
    assert is_pdf(b"") is False


def test_coerce_images_single_and_list():
    from services.vision_extractor import _coerce_images
    assert _coerce_images(b"abc") == [b"abc"]
    assert _coerce_images([b"a", b"b"]) == [b"a", b"b"]
    # falsy entries are dropped so an empty page never reaches the model
    assert _coerce_images([b"a", b"", None]) == [b"a"]


def test_strip_fences_both_extractors():
    from services.llm_extractor import _strip_fences as s1
    from services.vision_extractor import _strip_fences as s2
    fenced = '```json\n{"a": 1}\n```'
    assert s1(fenced) == '{"a": 1}'
    assert s2(fenced) == '{"a": 1}'


# ── PDF rendering / counting (needs poppler; skip if absent) ─────────────────────

def test_pdf_page_count_two_pages():
    pytest.importorskip("pdfplumber")
    from services.ocr_extractor import pdf_page_count
    assert pdf_page_count(_make_pdf(2)) == 2


def test_pdf_to_pngs_renders_every_page():
    pytest.importorskip("pdf2image")
    from services.ocr_extractor import pdf_to_pngs
    pages = pdf_to_pngs(_make_pdf(3), dpi=72)
    if not pages:
        pytest.skip("poppler/pdftoppm not installed")
    assert len(pages) == 3
    Image = pytest.importorskip("PIL.Image")
    for p in pages:
        assert Image.open(io.BytesIO(p)).format == "PNG"


def test_pdf_to_pngs_respects_max_pages():
    pytest.importorskip("pdf2image")
    from services.ocr_extractor import pdf_to_pngs
    pages = pdf_to_pngs(_make_pdf(5), dpi=72, max_pages=2)
    if not pages:
        pytest.skip("poppler/pdftoppm not installed")
    assert len(pages) == 2


def test_pdf_first_page_helper():
    pytest.importorskip("pdf2image")
    from services.ocr_extractor import pdf_first_page_to_png
    png = pdf_first_page_to_png(_make_pdf(4), dpi=72)
    if not png:
        pytest.skip("poppler/pdftoppm not installed")
    Image = pytest.importorskip("PIL.Image")
    assert Image.open(io.BytesIO(png)).format == "PNG"
