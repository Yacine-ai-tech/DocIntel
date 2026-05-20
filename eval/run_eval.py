"""
DocIntel eval harness — compares routes A/B/C on a benchmark dataset.

Usage:
    python eval/run_eval.py --dataset eval/invoices_eval.jsonl --route vision_premium

Each line in the dataset jsonl is:
    {"file": "01.pdf", "expected": {"vendor": "...", "total": 123.45, ...}}
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.vision_extractor import extract_via_vision_llm  # noqa: E402


async def run_route(route: str, dataset_path: str, image_dir: str) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    with open(dataset_path) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    for row in rows:
        path = Path(image_dir) / row["file"]
        if not path.exists():
            results.append({"file": row["file"], "error": "missing"})
            continue
        img = path.read_bytes()
        fields = await extract_via_vision_llm(img, doc_type="invoice")
        results.append({
            "file": row["file"],
            "expected": row["expected"],
            "actual": fields,
        })
    return {"route": route, "n": len(results), "results": results}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True)
    p.add_argument("--image-dir", required=True)
    p.add_argument("--route", default="vision_premium")
    p.add_argument("--output", default="eval/results.json")
    args = p.parse_args()

    out = asyncio.run(run_route(args.route, args.dataset, args.image_dir))
    Path(args.output).write_text(json.dumps(out, indent=2))
    print(f"Wrote {args.output} (n={out['n']})")


if __name__ == "__main__":
    main()
