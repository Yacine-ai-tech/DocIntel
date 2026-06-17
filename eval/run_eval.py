"""DocIntel eval harness — runs the vision route on a dataset and scores key-field accuracy.

Dataset jsonl line:  {"file": "inv_01.png", "expected": {"vendor": ..., "total": ..., ...}}

Usage:
    python eval/run_eval.py --dataset eval/invoices_eval.jsonl --image-dir eval/synthetic_invoices
    # gates: exits 1 if overall key-field accuracy < --threshold (default 0.85)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scoring import KEY_FIELDS, score_fields  # noqa: E402
from services.vision_extractor import extract_via_vision_llm  # noqa: E402


async def run_route(route: str, dataset_path: str, image_dir: str) -> Dict[str, Any]:
    with open(dataset_path) as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    results: List[Dict[str, Any]] = []
    for row in rows:
        path = Path(image_dir) / row["file"]
        if not path.exists():
            results.append({"file": row["file"], "error": "missing"})
            continue
        actual = await extract_via_vision_llm(path.read_bytes(), doc_type="invoice")
        results.append({"file": row["file"], "expected": row["expected"], "actual": actual,
                        "fields": score_fields(row["expected"], actual or {})})
    return {"route": route, "n": len(results), "results": results}


def summarize(out: Dict[str, Any]) -> Dict[str, Any]:
    scored = [r for r in out["results"] if "fields" in r]
    per_field = {k: 0 for k in KEY_FIELDS}
    total_correct = total_fields = 0
    for r in scored:
        for k in KEY_FIELDS:
            ok = bool(r["fields"].get(k))
            per_field[k] += int(ok)
            total_correct += int(ok)
            total_fields += 1
    n = max(1, len(scored))
    return {
        "docs": len(scored),
        "per_field_accuracy": {k: round(per_field[k] / n, 3) for k in KEY_FIELDS},
        "overall_key_field_accuracy": round(total_correct / max(1, total_fields), 3),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="eval/invoices_eval.jsonl")
    p.add_argument("--image-dir", default="eval/synthetic_invoices")
    p.add_argument("--route", default="vision_premium")
    p.add_argument("--output", default="eval/results.json")
    p.add_argument("--threshold", type=float, default=0.85)
    args = p.parse_args()

    out = asyncio.run(run_route(args.route, args.dataset, args.image_dir))
    summary = summarize(out)
    out["summary"] = summary
    Path(args.output).write_text(json.dumps(out, indent=2))

    print(f"\nDocIntel eval — route={args.route} docs={summary['docs']}")
    for k, v in summary["per_field_accuracy"].items():
        print(f"  {k:16} {v:.1%}")
    acc = summary["overall_key_field_accuracy"]
    print(f"\n  OVERALL key-field accuracy: {acc:.1%}  (threshold {args.threshold:.0%})")
    if acc < args.threshold:
        print("  ⚠️  below threshold")
        sys.exit(1)
    print("  ✅ pass")


if __name__ == "__main__":
    main()
