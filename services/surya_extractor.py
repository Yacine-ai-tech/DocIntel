"""
SuryaExtractor — layout-aware OCR via the `surya-ocr` library (text + bounding boxes + reading
order), the modern open-source successor to plain Tesseract for the OCR route.

The OCR path is now a *fallback* behind vision-first, but for clean scanned documents Surya
gives much better layout fidelity than Tesseract (proper reading order, tables, multi-column).

Off by default (SURYA_ENABLED=false) — Surya's real dependency chain is torch + torchvision +
transformers, the same class of heavy ML stack Route B's Ollama models are, and this module
degrades to a stub (falls through to Tesseract) rather than installing/loading it uninvited,
exactly like MarkerExtractor. Two deployment modes when enabled, mirroring Route B's
local/remote split exactly (services/route_b.py):

  SURYA_ENABLED=true            — turn Surya on at all (default false: skip straight to Tesseract)
  SURYA_MODE=local (default)    — surya-ocr installed in this same process (see requirements-ml.txt)
  SURYA_MODE=remote             — offload to an OCR-serving HTTP endpoint you host yourself
      SURYA_REMOTE_ENDPOINT      — POST {endpoint}/ocr with {"image_b64": "..."}, expects
                                    {"text": "...", "lines": [...]} back — the exact shape this
                                    class already returns locally, so callers can't tell local
                                    from remote from the response. Generic contract: any server
                                    implementing it works, no orchestrator-specific concept here.
      SURYA_REMOTE_TOKEN         — optional bearer token, if your endpoint requires auth
      SURYA_REMOTE_TIMEOUT       — seconds, default 60
"""
from __future__ import annotations

import io
import os
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


def _enabled() -> bool:
    return os.environ.get("SURYA_ENABLED", "").strip().lower() in ("1", "true", "yes")


def _mode() -> str:
    return os.environ.get("SURYA_MODE", "local").strip().lower()


class SuryaExtractor:
    """Layout-aware OCR (text lines + bboxes) using Surya. Lazy-loads local models on first
    call; makes no local-model attempt at all in remote mode."""

    def __init__(self, langs: Optional[List[str]] = None):
        self.langs = langs or ["en"]
        self._rec: Optional[Any] = None
        self._det: Optional[Any] = None

    def _ensure_models(self) -> None:
        """Called eagerly at startup (api.py's warm-up) so the first real request isn't slow.
        No-ops unless local mode is actually enabled — remote mode has nothing local to load,
        and the disabled default shouldn't pay any startup cost for a feature that's off."""
        if not _enabled() or _mode() != "local":
            return
        if self._rec is None and _SURYA:
            log.info("Loading Surya detection + recognition models (first call only)...")
            self._det = DetectionPredictor()
            # surya recent: RecognitionPredictor(FoundationPredictor()); older: no-arg
            try:
                from surya.foundation import FoundationPredictor
                self._rec = RecognitionPredictor(FoundationPredictor())
            except Exception:
                self._rec = RecognitionPredictor()

    def extract(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Run layout-aware OCR on a single page image.

        Returns:
            {"text": str, "lines": [{"text", "bbox", "confidence"}], "method": "surya"}
            or an error dict (stub) when disabled, unavailable, or the call fails.
        """
        if not _enabled():
            return {"text": "", "lines": [], "error": "surya_disabled", "method": "surya"}
        if _mode() == "remote":
            return self._extract_remote(image_bytes)
        return self._extract_local(image_bytes)

    def _extract_local(self, image_bytes: bytes) -> Dict[str, Any]:
        if not _SURYA or not _PIL:
            return {"text": "", "lines": [], "error": "surya_not_installed", "method": "surya"}
        try:
            self._ensure_models()
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            # surya's recognition signature has churned — try the known variants in order.
            preds = None
            for call in (lambda: self._rec([img], det_predictor=self._det),
                         lambda: self._rec([img], full_page=True),
                         lambda: self._rec([img])):
                try:
                    preds = call()
                    break
                except TypeError:
                    continue
            if preds is None:
                return {"text": "", "lines": [], "error": "surya_api_mismatch", "method": "surya"}
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

    def _extract_remote(self, image_bytes: bytes) -> Dict[str, Any]:
        endpoint = os.environ.get("SURYA_REMOTE_ENDPOINT", "").strip()
        if not endpoint:
            return {"text": "", "lines": [], "error": "surya_remote_endpoint_not_set", "method": "surya"}
        token = os.environ.get("SURYA_REMOTE_TOKEN", "").strip()
        try:
            import base64, json as _json, urllib.request
            payload = _json.dumps({"image_b64": base64.b64encode(image_bytes).decode()}).encode()
            headers = {"Content-Type": "application/json", "User-Agent": "DocIntel/1.0 Surya-Remote"}
            if token:
                headers["Authorization"] = "Bearer " + token
            req = urllib.request.Request(endpoint.rstrip("/") + "/ocr", data=payload, headers=headers)
            timeout = float(os.environ.get("SURYA_REMOTE_TIMEOUT", "60"))
            resp = _json.loads(urllib.request.urlopen(req, timeout=timeout).read())
            return {
                "text": resp.get("text", ""),
                "lines": resp.get("lines", []),
                "method": "surya",
            }
        except Exception as e:
            log.warning("Surya remote OCR failed (%s): %s", endpoint, e)
            return {"text": "", "lines": [], "error": str(e), "method": "surya"}
