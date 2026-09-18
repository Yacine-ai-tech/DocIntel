"""DocIntel concurrency & throughput benchmark.

Measures how many documents DocIntel can process concurrently via the live
/extract HTTP endpoint, at varying concurrency levels (1, 4, 8, 16, 32).
Reports throughput (docs/sec), p50/p99 per-doc latency, and error rate at
each concurrency level.

This complements run_benchmark.py (which measures per-route field accuracy)
with pure throughput and stability under load.

Resumption: each concurrency-level result is written to a .jsonl cache.
A rerun skips any already-measured concurrency level. Zero duplicate spend.

Usage:
    python eval/run_concurrency_benchmark.py
    python eval/run_concurrency_benchmark.py --api-url https://docintel-f4g1.onrender.com
    python eval/run_concurrency_benchmark.py --concurrency 1 4 8 16
    python eval/run_concurrency_benchmark.py --docs-per-level 20
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "eval"
BENCH_DIR = EVAL_DIR / "benchmark"
CACHE_FILE = EVAL_DIR / "cache" / "docintel_concurrency_cache.jsonl"

DEFAULT_API_URL = os.getenv("DOCINTEL_URL", "https://docintel-f4g1.onrender.com")
DEFAULT_CONCURRENCY_LEVELS = [1, 4, 8, 16, 32]
DEFAULT_DOCS_PER_LEVEL = 16  # docs per concurrency level


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_cache(cache_file: Path) -> set[str]:
    """Return set of already-benchmarked concurrency-level keys (e.g. 'c8')."""
    done: set[str] = set()
    if not cache_file.exists():
        return done
    with cache_file.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if "cache_key" in d:
                    done.add(d["cache_key"])
            except json.JSONDecodeError:
                pass
    return done


def _append_cache(cache_file: Path, record: dict) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with cache_file.open("a") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Document loading
# ---------------------------------------------------------------------------

def _load_sample_docs(n: int) -> list[dict]:
    """Load up to n documents from the ground-truth corpus."""
    gt_file = BENCH_DIR / "ground_truth.jsonl"
    if not gt_file.exists():
        # Fallback: create synthetic minimal docs for throughput testing
        print(f"[WARN] ground_truth.jsonl not found at {gt_file}")
        print("       Using synthetic health-check payloads for throughput measurement.")
        return [{"doc_type": "invoice", "synthetic": True, "idx": i} for i in range(n)]

    docs: list[dict] = []
    with gt_file.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                docs.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    # Cycle through corpus to reach n docs
    result = []
    for i in range(n):
        result.append(docs[i % len(docs)])
    return result


# ---------------------------------------------------------------------------
# Single-doc extraction via HTTP
# ---------------------------------------------------------------------------

async def _extract_one(
    client,
    api_url: str,
    doc: dict,
    doc_idx: int,
) -> dict:
    """Extract one document and return timing + outcome."""
    t0 = time.perf_counter()

    try:
        import io
        from PIL import Image

        if doc.get("synthetic"):
            # Health-check payload: POST to /health instead of /extract
            resp = await client.get(f"{api_url}/health", timeout=30.0)
            latency = time.perf_counter() - t0
            return {
                "doc_idx": doc_idx,
                "success": resp.status_code == 200,
                "status_code": resp.status_code,
                "latency_s": round(latency, 4),
                "error": None,
            }

        # Real doc: assemble page images into PDF and POST to /extract
        images_dir = BENCH_DIR / "images"
        if doc.get("all_pages"):
            img_paths = [images_dir / p for p in doc["all_pages"]]
        else:
            img_paths = [images_dir / doc["file"]]

        imgs_bytes = []
        for p in img_paths:
            if p.exists():
                imgs_bytes.append(p.read_bytes())

        if not imgs_bytes:
            return {
                "doc_idx": doc_idx,
                "success": False,
                "latency_s": round(time.perf_counter() - t0, 4),
                "error": "image_missing",
            }

        # Assemble PDF in memory
        pil_imgs = [Image.open(io.BytesIO(b)).convert("RGB") for b in imgs_bytes]
        buf = io.BytesIO()
        pil_imgs[0].save(buf, "PDF", save_all=True, append_images=pil_imgs[1:])
        pdf_bytes = buf.getvalue()

        resp = await client.post(
            f"{api_url}/extract",
            files={"file": (f"{doc.get('doc_type', 'invoice')}.pdf", pdf_bytes, "application/pdf")},
            data={"route": "ocr_fallback", "doc_type": doc.get("doc_type", "invoice")},
            timeout=60.0,
        )
        latency = time.perf_counter() - t0
        return {
            "doc_idx": doc_idx,
            "success": resp.status_code == 200,
            "status_code": resp.status_code,
            "latency_s": round(latency, 4),
            "error": None if resp.status_code == 200 else f"http_{resp.status_code}",
        }

    except Exception as exc:  # noqa: BLE001
        return {
            "doc_idx": doc_idx,
            "success": False,
            "latency_s": round(time.perf_counter() - t0, 4),
            "error": f"{type(exc).__name__}: {str(exc)[:120]}",
        }


# ---------------------------------------------------------------------------
# Concurrency-level benchmark
# ---------------------------------------------------------------------------

async def _bench_concurrency_level(
    api_url: str,
    concurrency: int,
    docs: list[dict],
) -> dict:
    """Run `docs` through the API with `concurrency` parallel slots."""
    try:
        import httpx
    except ImportError:
        print("[ERROR] httpx is required: pip install httpx[http2]", file=sys.stderr)
        sys.exit(1)

    try:
        from PIL import Image  # noqa: F401  # check available before run
    except ImportError:
        print("[WARN] Pillow not installed — using synthetic health-check payloads only.")

    semaphore = asyncio.Semaphore(concurrency)
    results: list[dict] = []
    t_wall_start = time.perf_counter()

    async with httpx.AsyncClient(http2=True, timeout=120.0) as client:
        async def _bounded(doc, idx):
            async with semaphore:
                return await _extract_one(client, api_url, doc, idx)

        tasks = [asyncio.create_task(_bounded(doc, i)) for i, doc in enumerate(docs)]
        results = await asyncio.gather(*tasks)

    wall_s = time.perf_counter() - t_wall_start
    latencies = sorted(r["latency_s"] for r in results)
    n = len(latencies)
    success = sum(1 for r in results if r["success"])

    return {
        "concurrency": concurrency,
        "docs_sent": n,
        "success": success,
        "errors": n - success,
        "error_rate_pct": round((n - success) / n * 100, 2) if n else 0,
        "wall_s": round(wall_s, 3),
        "throughput_docs_per_sec": round(n / wall_s, 3) if wall_s > 0 else 0,
        "latency_p50_s": round(latencies[n // 2], 4) if latencies else None,
        "latency_p95_s": round(latencies[int(n * 0.95)], 4) if latencies else None,
        "latency_p99_s": round(latencies[int(n * 0.99)], 4) if latencies else None,
        "latency_avg_s": round(sum(latencies) / n, 4) if latencies else None,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_concurrency_benchmark(
    api_url: str = DEFAULT_API_URL,
    concurrency_levels: list[int] = DEFAULT_CONCURRENCY_LEVELS,
    docs_per_level: int = DEFAULT_DOCS_PER_LEVEL,
    cache_file: Path = CACHE_FILE,
) -> dict:
    done_keys = _load_cache(cache_file)

    print("DocIntel Concurrency & Throughput Benchmark")
    print("=" * 60)
    print(f"API URL:  {api_url}")
    print(f"Levels:   {concurrency_levels}")
    print(f"Docs/level: {docs_per_level}")
    print(f"Cache:    {cache_file}")
    print(f"Already done: {done_keys}")
    print()

    # Warm up: confirm the service is alive
    try:
        import httpx
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.get(f"{api_url}/health")
            print(f"Health check: HTTP {r.status_code}")
    except Exception as exc:
        print(f"[WARN] Health check failed: {exc}")

    sample_docs = _load_sample_docs(docs_per_level)
    all_level_results: list[dict] = []

    for concurrency in concurrency_levels:
        cache_key = f"c{concurrency}"
        if cache_key in done_keys:
            print(f"  SKIP (cached)  concurrency={concurrency}")
            continue

        print(f"\n  Running concurrency={concurrency} with {docs_per_level} docs ...")
        level_result = await _bench_concurrency_level(api_url, concurrency, sample_docs)
        level_result["cache_key"] = cache_key

        _append_cache(cache_file, level_result)
        done_keys.add(cache_key)
        all_level_results.append(level_result)

        print(
            f"    throughput={level_result['throughput_docs_per_sec']:.2f} docs/s | "
            f"p50={level_result['latency_p50_s']}s | "
            f"p99={level_result['latency_p99_s']}s | "
            f"errors={level_result['errors']}/{level_result['docs_sent']}"
        )

    # Load all cached results for summary
    all_cached: list[dict] = []
    with cache_file.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    all_cached.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  {'Concurrency':>12}  {'Throughput':>14}  {'p50(s)':>8}  {'p99(s)':>8}  {'Errors':>8}")
    for r in sorted(all_cached, key=lambda x: x.get("concurrency", 0)):
        print(
            f"  {r['concurrency']:>12}  "
            f"{r['throughput_docs_per_sec']:>12.2f}/s  "
            f"{r.get('latency_p50_s', '?'):>8}  "
            f"{r.get('latency_p99_s', '?'):>8}  "
            f"{r.get('errors', '?'):>8}"
        )

    summary = {
        "benchmark": "DocIntel concurrency & throughput",
        "api_url": api_url,
        "levels": all_cached,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    summary_path = cache_file.parent / "docintel_concurrency_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\nSummary written to: {summary_path}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="DocIntel concurrency & throughput benchmark")
    parser.add_argument(
        "--api-url", default=DEFAULT_API_URL,
        help=f"DocIntel backend URL (default: {DEFAULT_API_URL})"
    )
    parser.add_argument(
        "--concurrency", type=int, nargs="+", default=DEFAULT_CONCURRENCY_LEVELS,
        metavar="N", help="Concurrency levels to test (default: 1 4 8 16 32)"
    )
    parser.add_argument(
        "--docs-per-level", type=int, default=DEFAULT_DOCS_PER_LEVEL,
        help=f"Docs per concurrency level (default: {DEFAULT_DOCS_PER_LEVEL})"
    )
    parser.add_argument(
        "--cache-file", type=Path, default=CACHE_FILE,
        help="Path to .jsonl cache file for resumption"
    )
    args = parser.parse_args()
    asyncio.run(run_concurrency_benchmark(
        api_url=args.api_url,
        concurrency_levels=args.concurrency,
        docs_per_level=args.docs_per_level,
        cache_file=args.cache_file,
    ))


if __name__ == "__main__":
    main()
