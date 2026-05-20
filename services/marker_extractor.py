"""
MarkerExtractor — High-quality PDF → Markdown via the `marker` library.

Used as the secondary route for table-heavy documents where Markdown output
is preferred over plain text.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.logger import get_logger

log = get_logger(__name__)

try:
    from marker.convert import convert_single_pdf
    from marker.models import load_all_models
    _MARKER = True
except ImportError:
    _MARKER = False
    log.warning("marker-pdf not installed — MarkerExtractor will return stubs")


class MarkerExtractor:
    """Convert PDFs to Markdown using the marker library."""

    def __init__(self):
        self._models: Optional[Any] = None

    def _ensure_models(self):
        if self._models is None and _MARKER:
            log.info("Loading marker models (first call only)...")
            self._models = load_all_models()

    def convert(self, pdf_path: str) -> Dict[str, Any]:
        """
        Convert a PDF file to Markdown.

        Args:
            pdf_path: Filesystem path to the PDF.

        Returns:
            {"markdown": str, "metadata": dict, "method": "marker"}
        """
        if not _MARKER:
            return {"markdown": "", "error": "marker_not_installed", "method": "marker"}
        try:
            self._ensure_models()
            text, images, metadata = convert_single_pdf(pdf_path, self._models)
            return {
                "markdown": text,
                "metadata": metadata,
                "method": "marker",
                "num_images": len(images),
            }
        except Exception as e:
            log.exception("Marker conversion failed: %s", e)
            return {"markdown": "", "error": str(e), "method": "marker"}
