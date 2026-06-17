"""
MarkerExtractor — High-quality PDF → Markdown via the `marker-pdf` library.

Secondary route for table-heavy / layout-rich PDFs where Markdown is preferred over plain text.
Supports the marker-pdf **1.x** API (PdfConverter + text_from_rendered) and falls back to the
old 0.x API; degrades to a stub when marker-pdf isn't installed.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.logger import get_logger

log = get_logger(__name__)

_MARKER_API: Optional[str] = None
try:  # marker-pdf 1.x
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered
    _MARKER = True
    _MARKER_API = "v1"
except ImportError:
    try:  # marker-pdf 0.x
        from marker.convert import convert_single_pdf
        from marker.models import load_all_models
        _MARKER = True
        _MARKER_API = "v0"
    except ImportError:
        _MARKER = False
        log.warning("marker-pdf not installed — MarkerExtractor will return stubs")


class MarkerExtractor:
    """Convert PDFs to Markdown using marker-pdf (lazy model load on first call)."""

    def __init__(self):
        self._obj: Optional[Any] = None  # converter (v1) or models (v0)

    def _ensure(self):
        if self._obj is None and _MARKER:
            log.info("Loading marker models (first call only)...")
            self._obj = PdfConverter(artifact_dict=create_model_dict()) if _MARKER_API == "v1" \
                else load_all_models()

    def convert(self, pdf_path: str) -> Dict[str, Any]:
        """Convert a PDF to Markdown → {"markdown", "method": "marker", "num_images"} (or error)."""
        if not _MARKER:
            return {"markdown": "", "error": "marker_not_installed", "method": "marker"}
        try:
            self._ensure()
            if _MARKER_API == "v1":
                rendered = self._obj(pdf_path)
                text, _meta, images = text_from_rendered(rendered)
                return {"markdown": text, "method": "marker", "num_images": len(images or [])}
            text, images, metadata = convert_single_pdf(pdf_path, self._obj)
            return {"markdown": text, "metadata": metadata, "method": "marker",
                    "num_images": len(images)}
        except Exception as e:
            log.exception("Marker conversion failed: %s", e)
            return {"markdown": "", "error": str(e), "method": "marker"}
