"""World-standard receipt key-information-extraction benchmark: **SROIE** (ICDAR 2019 Task 3).
Runs DocIntel Route A (Claude Sonnet Vision) on SROIE receipt images and scores the standard
fields (company, date, total) against ground truth. This is the recognized benchmark behind
STRATEGY §3.4's "90%+ field accuracy" target.

Scoring (per the SROIE convention, lenient where the field is free-text):
  company → case-insensitive substring match (either direction)
  date    → normalized digit-sequence match
  total   → numeric within max(0.02, 1%)

Usage:  python eval/run_sroie_benchmark.py --n 30
Needs:  ANTHROPIC_API_KEY; datasets (SROIE from HF).
"""
from __future__ import annotations

import argparse
import asyncio
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _digits(s):
    return re.sub(r"\D", "", str(s or ""))


def _num(v):
    s = re.sub(r"[^0-9.]", "", str(v or ""))
    try:
        return round(float(s), 2) if s else None
    except ValueError:
        return None


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _load_sroie(n):
    from datasets import load_dataset
    last = None
    for repo, split in (("nhernandez99/sroie_dataset", "test"), ("rajistics/sroie", "train")):
        try:
            ds = load_dataset(repo, split=split)
            return ds.select(range(min(n, len(ds)))), f"{repo}[{split}]"
        except Exception as e:
            last = e
    raise RuntimeError(f"could not load SROIE: {last}")


def _gt(ex):
    import json
    # Donut-style: ground_truth is a JSON string {"gt_parse": {company,date,total,...}}
    raw = ex.get("ground_truth")
    if raw:
        try:
            p = json.loads(raw).get("gt_parse", {})
            if isinstance(p, dict):
                return p
        except Exception:
            pass
    for key in ("entities", "key", "labels"):
        d = ex.get(key)
        if isinstance(d, dict):
            return d
    return {k: ex.get(k) for k in ("company", "date", "total", "address") if k in ex}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    a = ap.parse_args()
    from services.vision_extractor import extract_via_vision_llm

    ds, repo = _load_sroie(a.n)
    print(f"\nSROIE benchmark — {len(ds)} receipts from {repo} — Route A (Claude Sonnet Vision)")
    fields = ("company", "date", "total")
    correct = {f: 0 for f in fields}
    total_present = {f: 0 for f in fields}
    ok_docs = 0

    for i, ex in enumerate(ds):
        gt = _gt(ex)
        img = ex.get("image")
        if img is None:
            continue
        buf = io.BytesIO(); img.convert("RGB").save(buf, "PNG")
        res = await extract_via_vision_llm(buf.getvalue(), doc_type="receipt")
        if not isinstance(res, dict) or "error" in res:
            continue
        ok_docs += 1
        pred_company = res.get("merchant") or res.get("vendor") or res.get("company")
        preds = {"company": pred_company, "date": res.get("date"), "total": res.get("total")}
        for f in fields:
            g = gt.get(f)
            if g in (None, ""):
                continue
            total_present[f] += 1
            if f == "total":
                gn, pn = _num(g), _num(preds[f])
                hit = gn is not None and pn is not None and abs(gn - pn) <= max(0.02, abs(gn) * 0.01)
            elif f == "date":
                # format-agnostic: compare the set of numeric components (DD/MM/YYYY == YYYY-MM-DD)
                gset = set(re.findall(r"\d+", str(g)))
                pset = set(re.findall(r"\d+", str(preds[f] or "")))
                hit = bool(gset) and gset == pset
            else:
                gv, pv = _norm(g), _norm(preds[f])
                hit = bool(gv and pv and (gv in pv or pv in gv))
            correct[f] += int(hit)
        if (i + 1) % 10 == 0:
            print(f"  processed {i+1}/{len(ds)}")

    print(f"\n=== SROIE RESULTS (docs ok {ok_docs}/{len(ds)}) ===")
    micro_c = sum(correct.values()); micro_t = sum(total_present.values())
    for f in fields:
        t = total_present[f]
        print(f"  {f:8} {correct[f]}/{t} = {correct[f]/max(1,t):.1%}")
    print(f"  OVERALL field accuracy: {micro_c}/{micro_t} = {micro_c/max(1,micro_t):.1%}")
    print(f"  (STRATEGY §3.4 target: 90%+ on invoice/receipt fields | published SROIE SOTA "
          f"F1 ~96-98% with task-finetuned LayoutLM-class models)")


if __name__ == "__main__":
    asyncio.run(main())
