"""Verify the 100+ page pipeline end-to-end on the generated large PDF.

Renders/parses every page, runs a route (which chunks + merges internally), and checks that
the header fields (page 1) AND the grand total (last page) are both recovered — proving
cross-chunk aggregation. Prints page_count, chunk count, and per-field correctness.

Usage:
  python eval/verify_large_doc.py --route ocr_fallback     # cheap (Tesseract/native text + Haiku)
  python eval/verify_large_doc.py --route vision_premium   # Claude vision (chunked)
  python eval/verify_large_doc.py --route vision_local      # Ollama vision (chunked, GPU)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
LD = ROOT / "eval" / "large_doc"


def _num(v):
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = re.sub(r"[^0-9.\-]", "", str(v or ""))
    try:
        return round(float(s), 2) if s not in ("", "-", ".") else None
    except ValueError:
        return None


def _score(expected, actual):
    actual = actual or {}
    r = {}
    for k, v in expected.items():
        if k in ("subtotal", "tax", "total"):
            en, an = _num(v), _num(actual.get(k))
            r[k] = en is not None and an is not None and abs(en - an) <= max(0.02, abs(en) * 0.01)
        elif k == "vendor":
            ev, av = str(v).lower(), str(actual.get("vendor") or "").lower()
            r[k] = bool(ev and av and (ev[:12] in av or av[:12] in ev))
        else:
            r[k] = str(v).strip().lower() == str(actual.get(k) or "").strip().lower()
    return r


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", default="ocr_fallback")
    a = ap.parse_args()

    from core.config import settings
    from services.ocr_extractor import extract_text_from_pdf, pdf_page_count, pdf_to_pngs

    row = json.loads((LD / "large_eval.jsonl").read_text().strip())
    pdf = (LD / row["file"]).read_bytes()
    n = pdf_page_count(pdf)
    print(f"\nLarge-doc verify — {row['file']} — {n} pages — route={a.route}")

    if a.route == "ocr_fallback":
        from services.llm_extractor import LLMExtractor
        text = extract_text_from_pdf(pdf, max_pages=settings.MAX_PDF_PAGES)
        fields = await LLMExtractor(model=settings.LLM_CLEANUP).extract(text, "invoice")
    else:
        from services.vision_extractor import extract_via_vision_llm
        imgs = pdf_to_pngs(pdf, max_pages=settings.MAX_PDF_PAGES)
        model = settings.LLM_VISION_LOCAL if a.route == "vision_local" else None
        fields = await extract_via_vision_llm(imgs, model=model, doc_type="invoice")

    if not isinstance(fields, dict) or "error" in fields:
        print("  EXTRACTION ERROR:", fields)
        return
    sc = _score(row["expected"], fields)
    print(f"  pages={fields.get('_pages', n)}  chunks={fields.get('_chunks', 1)}")
    for k, ok in sc.items():
        exp = row["expected"][k]
        got = fields.get(k)
        print(f"    {k:16} {'✓' if ok else '✗'}  expected={exp!r:40} got={got!r}")
    print(f"  OVERALL: {sum(sc.values())}/{len(sc)} fields correct")
    print("  → header (page 1) + grand total (last page) both recovered = cross-chunk merge works"
          if sc.get("vendor") and sc.get("total") else "  → check merge: header/total not both recovered")


if __name__ == "__main__":
    asyncio.run(main())
