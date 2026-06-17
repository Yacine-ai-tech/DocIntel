"""
OCR & Document Processing Enhancement — Beyond images to full PDF extraction.

Features:
- PDF text extraction (already in omnismart_chatbot)
- Table detection & extraction from PDFs
- Form field identification
- Handwritten text OCR (if image processing available)
- Document classification
- Structured data extraction (invoices, contracts, reports)
- Layout analysis & segmentation
"""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger

log = get_logger(__name__)

# Try to import optional OCR libraries
try:
    import pytesseract
    from PIL import Image
    _TESSERACT = True
except ImportError:
    _TESSERACT = False

try:
    import pdfplumber
    _PDFPLUMBER = True
except ImportError:
    _PDFPLUMBER = False

try:
    import pdf2image
    _PDF2IMAGE = True
except ImportError:
    _PDF2IMAGE = False


import os as _os

# Tesseract language packs to try (install the matching tesseract-ocr-<lang> packages).
# Falls back to "eng" automatically if a pack is missing.
_OCR_LANGS = _os.getenv("OCR_LANGS", "eng+fra+deu+nld+spa+ita")


def extract_text_from_image(image_bytes: bytes, lang: Optional[str] = None) -> str:
    """Route C (Tesseract): plain OCR of an image's text. ``lang`` is a Tesseract language
    string like "eng+fra"; defaults to ``OCR_LANGS``. Returns '' when Tesseract isn't
    available or finds no text — the caller decides how to degrade."""
    if not _TESSERACT:
        log.warning("pytesseract/Tesseract not installed — OCR route unavailable")
        return ""
    langs = lang or _OCR_LANGS
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        try:
            return pytesseract.image_to_string(img, lang=langs).strip()
        except pytesseract.TesseractError:
            # A requested language pack isn't installed — degrade to English.
            log.warning("Tesseract langs %r unavailable — falling back to eng", langs)
            return pytesseract.image_to_string(img, lang="eng").strip()
    except Exception as e:
        log.error("OCR (Tesseract) failed: %s", e)
        return ""


def is_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def pdf_page_count(pdf_bytes: bytes) -> int:
    """Number of pages in a PDF (0 if it can't be read)."""
    if _PDFPLUMBER:
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                return len(pdf.pages)
        except Exception as e:
            log.error("pdf_page_count (pdfplumber) failed: %s", e)
    if _PDF2IMAGE:
        try:
            from pdf2image.pdf2image import pdfinfo_from_bytes
            return int(pdfinfo_from_bytes(pdf_bytes).get("Pages", 0))
        except Exception as e:
            log.error("pdf_page_count (pdfinfo) failed: %s", e)
    return 0


def pdf_to_pngs(pdf_bytes: bytes, dpi: int = 150, max_pages: int = 20) -> List[bytes]:
    """Render **every** page of a PDF to PNG bytes (capped at ``max_pages`` for cost/safety).

    This is what makes the vision routes multi-page: each page becomes one image and all
    images are sent to the vision LLM in a single request so it can reason across pages
    (e.g. an invoice whose totals sit on a later page, or a multi-page contract).
    Returns [] if rendering is unavailable.
    """
    if not _PDF2IMAGE:
        log.warning("pdf2image/poppler not installed — cannot render PDF to image")
        return []
    try:
        last = max_pages if max_pages and max_pages > 0 else None
        pages = pdf2image.convert_from_bytes(pdf_bytes, dpi=dpi, first_page=1, last_page=last)
        out: List[bytes] = []
        for page in pages:
            buf = io.BytesIO()
            page.save(buf, "PNG")
            out.append(buf.getvalue())
        return out
    except Exception as e:
        log.error("PDF→PNG render failed: %s", e)
        return []


def pdf_first_page_to_png(pdf_bytes: bytes, dpi: int = 150) -> bytes:
    """Render page 1 of a PDF to PNG bytes (back-compat helper). Returns b'' if unavailable."""
    pages = pdf_to_pngs(pdf_bytes, dpi=dpi, max_pages=1)
    return pages[0] if pages else b""


def extract_text_from_pdf(pdf_bytes: bytes, max_pages: int = 50, ocr_dpi: int = 200) -> str:
    """Full-document text for the OCR route. Uses pdfplumber's native text layer across all
    pages; for scanned PDFs with no embedded text it falls back to rendering each page and
    running Tesseract. Pages are separated by a form-feed marker so the LLM sees boundaries.
    """
    parts: List[str] = []
    if _PDFPLUMBER:
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages[:max_pages]:
                    parts.append(page.extract_text() or "")
        except Exception as e:
            log.error("extract_text_from_pdf (pdfplumber) failed: %s", e)
    native = "\n\f\n".join(parts).strip()
    if native:
        return native
    # Scanned PDF (no text layer) → OCR each rendered page.
    if _TESSERACT and _PDF2IMAGE:
        log.info("PDF has no text layer — falling back to per-page Tesseract OCR")
        imgs = pdf_to_pngs(pdf_bytes, dpi=ocr_dpi, max_pages=max_pages)
        return "\n\f\n".join(extract_text_from_image(img) for img in imgs).strip()
    return ""


# ════════════════════════════════════════════════════════════════════════════
# PDF TABLE EXTRACTION
# ════════════════════════════════════════════════════════════════════════════

class PDFTableExtractor:
    """Extract tables from PDF files."""

    @staticmethod
    def extract_tables(pdf_content: io.BytesIO) -> List[List[List[str]]]:
        """
        Extract all tables from PDF.
        
        Returns: List of tables, each table is a list of rows
        """
        if not _PDFPLUMBER:
            log.warning("pdfplumber not installed, skipping table extraction")
            return []

        tables = []
        try:
            with pdfplumber.open(pdf_content) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
            log.info("Extracted %d tables from PDF", len(tables))
        except Exception as e:
            log.error("Table extraction error: %s", e)

        return tables

    @staticmethod
    def detect_table_regions(pdf_content: io.BytesIO) -> List[Dict[str, Any]]:
        """
        Detect table regions in PDF (bounding boxes).
        
        Returns: List of regions with coordinates
        """
        if not _PDFPLUMBER:
            return []

        regions = []
        try:
            with pdfplumber.open(pdf_content) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_tables = page.extract_tables(layout_mode="lines")
                    if page_tables:
                        for table in page_tables:
                            regions.append({
                                "page": page_num,
                                "table": table,
                                "bbox": page.bbox,
                            })
        except Exception as e:
            log.error("Table region detection error: %s", e)

        return regions


# ════════════════════════════════════════════════════════════════════════════
# FORM FIELD DETECTION
# ════════════════════════════════════════════════════════════════════════════

class FormFieldDetector:
    """Detect and extract form fields from documents."""

    @staticmethod
    def detect_form_fields(pdf_content: io.BytesIO) -> List[Dict[str, Any]]:
        """
        Detect form fields (text boxes, checkboxes, radio buttons).
        
        Returns: List of detected fields with coordinates and types
        """
        if not _PDFPLUMBER:
            return []

        fields = []
        try:
            with pdfplumber.open(pdf_content) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Extract lines that might be form field boxes
                    rects = page.rects
                    for rect in rects:
                        fields.append({
                            "page": page_num,
                            "type": "text_field",
                            "bbox": rect,
                            "coordinates": {
                                "x0": rect.x0,
                                "y0": rect.y0,
                                "x1": rect.x1,
                                "y1": rect.y1,
                            },
                        })
        except Exception as e:
            log.error("Form field detection error: %s", e)

        return fields

    @staticmethod
    def extract_form_values(
        pdf_content: io.BytesIO,
        field_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Extract form field values.
        
        For fillable PDFs, returns field values.
        For non-fillable PDFs, attempts text extraction from field regions.
        """
        values = {}
        try:
            with pdfplumber.open(pdf_content) as pdf:
                # Try to get form fields if PDF is fillable
                if hasattr(pdf, "get_fields") and callable(pdf.get_fields):
                    try:
                        fields = pdf.get_fields()
                        for field_name, field_data in fields.items():
                            if not field_names or field_name in field_names:
                                values[field_name] = field_data.get("value")
                    except Exception:
                        pass

                # Fallback: extract text from all regions
                if not values:
                    for page in pdf.pages:
                        text = page.extract_text()
                        values["full_text"] = text

        except Exception as e:
            log.error("Form value extraction error: %s", e)

        return values


# ════════════════════════════════════════════════════════════════════════════
# HANDWRITTEN TEXT OCR
# ════════════════════════════════════════════════════════════════════════════

class HandwritingOCR:
    """OCR for handwritten text in documents."""

    @staticmethod
    def extract_handwriting(image_bytes: io.BytesIO, language: str = "eng") -> str:
        """
        Extract handwritten text from image using Tesseract.
        
        Language codes: 'eng' (English), 'fra' (French), 'deu' (German), etc.
        """
        if not _TESSERACT:
            log.warning("pytesseract/Tesseract not installed, skipping handwriting OCR")
            return ""

        try:
            image = Image.open(image_bytes)
            # Preprocess for better OCR
            image = image.convert("RGB")

            # Extract text
            text = pytesseract.image_to_string(image, lang=language)
            log.info("Extracted handwritten text (%s): %d characters", language, len(text))
            return text
        except Exception as e:
            log.error("Handwriting OCR error: %s", e)
            return ""

    @staticmethod
    def detect_handwriting_regions(image_bytes: io.BytesIO) -> List[Dict[str, Any]]:
        """
        Detect regions containing handwritten text.
        
        Returns: List of regions with confidence scores
        """
        if not _TESSERACT:
            return []

        regions = []
        try:
            image = Image.open(image_bytes)
            # Use Tesseract data to detect regions
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

            # Group by confidence
            for idx, conf in enumerate(data["conf"]):
                if int(conf) > 50:  # Confidence threshold
                    regions.append({
                        "bbox": {
                            "x": data["left"][idx],
                            "y": data["top"][idx],
                            "width": data["width"][idx],
                            "height": data["height"][idx],
                        },
                        "confidence": int(conf),
                        "text": data["text"][idx],
                    })

            log.info("Detected %d handwriting regions", len(regions))
        except Exception as e:
            log.error("Handwriting region detection error: %s", e)

        return regions


# ════════════════════════════════════════════════════════════════════════════
# DOCUMENT CLASSIFICATION
# ════════════════════════════════════════════════════════════════════════════

class DocumentClassifier:
    """Classify documents by type (invoice, contract, report, etc.)."""

    DOCUMENT_TYPES = {
        "invoice": {
            "keywords": ["invoice", "inv-", "bill", "payment", "amount due", "total"],
            "patterns": [r"INV[-\s]*\d{4,}", r"Invoice\s*#"],
        },
        "contract": {
            "keywords": ["agreement", "contract", "terms", "conditions", "parties", "obligations"],
            "patterns": [r"agreement\s+date", r"party\s+of\s+the\s+first\s+part"],
        },
        "report": {
            "keywords": ["report", "summary", "analysis", "findings", "recommendations"],
            "patterns": [r"annual\s+report", r"financial\s+report"],
        },
        "receipt": {
            "keywords": ["receipt", "store", "total", "payment", "items", "thank you"],
            "patterns": [r"receipt\s*#", r"transaction\s+id"],
        },
        "form": {
            "keywords": ["form", "complete", "signature", "date", "please"],
            "patterns": [r"form\s+\d{3,}", r"application\s+form"],
        },
    }

    @staticmethod
    def classify_document(text: str) -> Tuple[str, float]:
        """
        Classify document by analyzing text content.
        
        Returns: (document_type, confidence)
        """
        text_lower = text.lower()
        scores = {}

        for doc_type, patterns_dict in DocumentClassifier.DOCUMENT_TYPES.items():
            score = 0

            # Count keyword matches
            for keyword in patterns_dict.get("keywords", []):
                if keyword in text_lower:
                    score += 1

            # Check pattern matches (use simple string search, not regex for speed)
            for pattern_keywords in patterns_dict.get("patterns", []):
                # Convert regex pattern to keywords
                keywords_from_pattern = pattern_keywords.replace(r"\s+", " ").split()
                for keyword in keywords_from_pattern:
                    if keyword in text_lower:
                        score += 2

            scores[doc_type] = score

        if not scores or max(scores.values()) == 0:
            return "general", 0.3

        best_type = max(scores, key=scores.get)
        confidence = min(0.99, scores[best_type] / 5)

        return best_type, confidence

    @staticmethod
    def classify_from_pdf(pdf_content: io.BytesIO) -> Tuple[str, float]:
        """
        Classify PDF document.
        """
        text = ""
        try:
            if _PDFPLUMBER:
                with pdfplumber.open(pdf_content) as pdf:
                    # Get first few pages
                    for page in pdf.pages[:3]:
                        text += page.extract_text() or ""
            else:
                log.warning("pdfplumber not available, classification may be limited")
        except Exception as e:
            log.error("PDF classification error: %s", e)

        return DocumentClassifier.classify_document(text)


# ════════════════════════════════════════════════════════════════════════════
# UNIFIED OCR & DOCUMENT PROCESSOR
# ════════════════════════════════════════════════════════════════════════════

class EnhancedDocumentProcessor:
    """Unified processor for full document handling."""

    def __init__(self):
        self.table_extractor = PDFTableExtractor()
        self.form_detector = FormFieldDetector()
        self.handwriting_ocr = HandwritingOCR()
        self.classifier = DocumentClassifier()

    def process_pdf(self, pdf_content: io.BytesIO) -> Dict[str, Any]:
        """
        Comprehensive PDF processing.
        
        Returns: Full document analysis with text, tables, forms, classification
        """
        result = {
            "document_type": None,
            "confidence": 0.0,
            "text": "",
            "tables": [],
            "form_fields": [],
            "metadata": {},
        }

        try:
            # Extract text
            if _PDFPLUMBER:
                with pdfplumber.open(pdf_content) as pdf:
                    for page in pdf.pages:
                        result["text"] += page.extract_text() or ""
                    result["metadata"]["page_count"] = len(pdf.pages)

            # Extract tables
            result["tables"] = self.table_extractor.extract_tables(pdf_content)

            # Detect form fields
            result["form_fields"] = self.form_detector.detect_form_fields(pdf_content)

            # Classify document
            doc_type, confidence = self.classifier.classify_document(result["text"])
            result["document_type"] = doc_type
            result["confidence"] = confidence

            log.info(
                "PDF processing complete: type=%s (%.1f%%), tables=%d, fields=%d",
                doc_type, confidence * 100, len(result["tables"]), len(result["form_fields"])
            )

        except Exception as e:
            log.error("PDF processing error: %s", e)

        return result

    def process_image(self, image_bytes: io.BytesIO) -> Dict[str, Any]:
        """
        Process image (handwriting extraction, text OCR).
        """
        result = {
            "text": "",
            "handwriting": "",
            "handwriting_regions": [],
            "metadata": {},
        }

        try:
            # General text OCR
            if _TESSERACT:
                image = Image.open(image_bytes)
                result["text"] = pytesseract.image_to_string(image)

                # Detect handwriting regions
                result["handwriting_regions"] = self.handwriting_ocr.detect_handwriting_regions(image_bytes)
                if result["handwriting_regions"]:
                    result["handwriting"] = " ".join([r.get("text", "") for r in result["handwriting_regions"]])

                result["metadata"]["image_size"] = image.size
                log.info("Image processing complete: text=%d chars, regions=%d", len(result["text"]), len(result["handwriting_regions"]))

        except Exception as e:
            log.error("Image processing error: %s", e)

        return result


__all__ = [
    "EnhancedDocumentProcessor",
    "PDFTableExtractor",
    "FormFieldDetector",
    "HandwritingOCR",
    "DocumentClassifier",
]

