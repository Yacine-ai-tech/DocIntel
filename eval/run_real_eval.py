"""Real-doc eval — runs a route on the downloaded real (multilingual) invoices and scores
ONLY the fields present in each ground-truth row (some real docs have totals on page 2, etc.).

Currency is normalized across symbol/code ($↔USD, €↔EUR, ₹↔INR, £↔GBP). Vendor is lenient
(substring), id/date exact, numerics within max(0.02, 1%).

Usage:
    python eval/run_real_eval.py --route vision_premium   # Route A (Claude Vision)
    python eval/run_real_eval.py --route ocr_fallback     # Route C (Tesseract + LLM)
    python eval/run_real_eval.py --route vision_local      # Route B (Ollama Llama Vision)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_CUR = {"$": "USD", "us$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR",
        "₹": "INR", "inr": "INR", "rs": "INR", "rs.": "INR", "£": "GBP", "gbp": "GBP"}


def _norm(s):
    return re.sub(r"\s+", " ", str(s if s is not None else "").strip().lower())


def _cur(v):
    s = _norm(v)
    return _CUR.get(s, s.upper() if len(s) == 3 else s)


def _num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = re.sub(r"[^0-9.\-]", "", str(v))
    try:
        return round(float(s), 2) if s not in ("", "-", ".") else None
    except ValueError:
        return None


def score_present(expected, actual):
    actual = actual or {}
    r = {}
    for k, v in expected.items():
        if k in ("subtotal", "tax", "total"):
            en, an = _num(v), _num(actual.get(k))
            r[k] = en is not None and an is not None and abs(en - an) <= max(0.02, abs(en) * 0.01)
        elif k == "currency":
            r[k] = _cur(v) == _cur(actual.get(k))
        elif k == "vendor":
            ev, av = _norm(v), _norm(actual.get("vendor"))
            r[k] = bool(ev and av and (ev in av or av in ev))
        else:  # invoice_number, date
            r[k] = _norm(v) == _norm(actual.get(k))
    return r


async def _extract(route, png_path):
    img = Path(png_path).read_bytes()
    if route == "ocr_fallback":
        from services.llm_extractor import LLMExtractor
        from services.ocr_extractor import extract_text_from_image
        text = extract_text_from_image(img)
        return await LLMExtractor().extract(text, "invoice") if text else {"error": "ocr_empty"}
    from services.vision_extractor import extract_via_vision_llm
    model = "ollama/llama3.2-vision" if route == "vision_local" else None
    return await extract_via_vision_llm(img, model=model, doc_type="invoice")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="eval/real_invoices_eval.jsonl")
    ap.add_argument("--image-dir", default="eval/real_invoices")
    ap.add_argument("--route", default="vision_premium")
    a = ap.parse_args()

    rows = [json.loads(line) for line in open(a.dataset) if line.strip()]
    tot = cor = 0
    per = {}
    print(f"\nReal-doc eval — route={a.route}")
    for row in rows:
        p = Path(a.image_dir) / row["file"]
        if not p.exists():
            print(f"  MISSING {row['file']}")
            continue
        sc = score_present(row["expected"], await _extract(a.route, p))
        ok, n = sum(sc.values()), len(sc)
        tot += n
        cor += ok
        for k, v in sc.items():
            per.setdefault(k, [0, 0])
            per[k][0] += int(v)
            per[k][1] += 1
        print(f"  [{row['lang']}] {row['file']:26} {ok}/{n}  " +
              " ".join(f"{k}{'✓' if v else '✗'}" for k, v in sc.items()))
    print(f"\n  OVERALL (present fields): {cor}/{tot} = {cor / max(1, tot):.1%}")
    for k, (c, t) in sorted(per.items()):
        print(f"    {k:16} {c}/{t}")


if __name__ == "__main__":
    asyncio.run(main())
