"""
SuryaExtractor — layout-aware OCR via the `surya-ocr` library (text + bounding boxes + reading
order), the modern open-source successor to plain Tesseract for the OCR route.

Per STRATEGY §3.10 the OCR path is now a *fallback* behind vision-first, but for clean scanned
documents Surya gives much better layout fidelity than Tesseract (proper reading order, tables,
multi-column). Heavy ML dep — lives in `requirements-ml.txt`; this module degrades to a stub
when surya isn't installed, exactly like `MarkerExtractor`.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger(__name__)

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

try:
    # surya 0.4+ predictor API
    from surya.detection import DetectionPredictor
    from surya.recognition import RecognitionPredictor
    _SURYA = True
except ImportError:
    _SURYA = False
    log.warning("surya-ocr not installed — SuryaExtractor will return stubs")


class SuryaExtractor:
    """Layout-aware OCR (text lines + bboxes) using Surya. Lazy-loads models on first call."""

    def __init__(self, langs: Optional[List[str]] = None):
        self.langs = langs or ["en"]
        self._rec: Optional[Any] = None
        self._det: Optional[Any] = None

    def _ensure_models(self) -> None:
        if self._rec is None and _SURYA:
            log.info("Loading Surya detection + recognition models (first call only)...")
            self._det = DetectionPredictor()
            self._rec = RecognitionPredictor()

    def extract(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Run layout-aware OCR on a single page image.

        Returns:
            {"text": str, "lines": [{"text", "bbox", "confidence"}], "method": "surya"}
            or an error dict (stub) when surya/PIL are unavailable.
        """
        if not _SURYA or not _PIL:
            return {"text": "", "lines": [], "error": "surya_not_installed", "method": "surya"}
        try:
            self._ensure_models()
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            # surya 0.6+ recognition API: full-page OCR (no separate det_predictor kwarg)
            try:
                preds = self._rec([img], full_page=True)
            except TypeError:
                preds = self._rec([img])  # older signature fallback
            page = preds[0]
            lines = [
                {"text": ln.text, "bbox": getattr(ln, "bbox", None),
                 "confidence": getattr(ln, "confidence", None)}
                for ln in getattr(page, "text_lines", [])
            ]
            return {
                "text": "\n".join(ln["text"] for ln in lines),
                "lines": lines,
                "method": "surya",
            }
        except Exception as e:
            log.exception("Surya OCR failed: %s", e)
            return {"text": "", "lines": [], "error": str(e), "method": "surya"}
