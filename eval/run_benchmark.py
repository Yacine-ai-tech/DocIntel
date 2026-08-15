"""Scale + accuracy benchmark over the 500+ document corpus (eval/benchmark/).

Two things matter for the pitch: ACCURACY (field-level, on the ground-truth subset) and
ROBUSTNESS AT SCALE (process hundreds/thousands of mixed real documents concurrently without
falling over). This runner measures both, with cost controls so a full run is affordable.

Modes:
  --scale-only        ingest+OCR every doc (NO LLM, free) → throughput + success rate at scale
  --route vision_route_a|vision_route_b|ocr_fallback   field extraction + accuracy on GT subset

Cost controls: --limit caps docs; --doc-type filters; --concurrency bounds fan-out. Route C
cleanup uses the cheap model from settings (Haiku by default).

Usage:
  python eval/run_benchmark.py --scale-only                          # free robustness pass
  python eval/run_benchmark.py --route ocr_fallback --limit 200      # broad, cheap accuracy
  python eval/run_benchmark.py --route vision_route_a --limit 40     # Claude accuracy sample
  python eval/run_benchmark.py --route vision_route_b --limit 40     # Ollama (local/self-hosted) sample

Remote mode (--api-url):
  Runs every doc through a real deployed DocIntel instance's HTTP API instead of importing
  services in-process. Exists because the dev/CI sandbox this repo is normally checked out into
  often lacks system deps only the Dockerfile installs (Tesseract for Route C and --scale-only,
  poppler for PDF rasterization) — the deployed instance always has them, since it's built from
  the same Dockerfile that ships to production. Multi-page docs (all_pages: multiple separate
  page images) are assembled into one in-memory PDF via Pillow before upload, since /extract
  takes one file and already does its own chunked multi-page handling.

  python eval/run_benchmark.py --scale-only --api-url https://docintel-mm79.onrender.com
  python eval/run_benchmark.py --route vision_route_a --api-url https://docintel-mm79.onrender.com --limit 40
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
BENCH = ROOT / "eval" / "benchmark"


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


def _norm(s):
    return re.sub(r"\s+", " ", str(s if s is not None else "").strip().lower())


_CUR = {"$": "USD", "us$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR", "₹": "INR",
        "inr": "INR", "rs": "INR", "rs.": "INR", "£": "GBP", "gbp": "GBP",
        # West/Central African CFA franc → XOF (West) / XAF (Central)
        "fcfa": "XOF", "cfa": "XOF", "f cfa": "XOF", "cfa f": "XOF", "xof": "XOF",
        "fcfa xof": "XOF", "xaf": "XAF", "₣": "XOF"}


def _cur(v):
    s = _norm(v)
    return _CUR.get(s, s.upper() if len(s) == 3 else s)


def score(doc_type, expected, actual):
    """Per-field correctness for the fields present in the ground truth."""
    actual = actual or {}
    r = {}
    for k, v in expected.items():
        if k in ("total", "subtotal", "tax", "amount"):
            en, an = _num(v), _num(actual.get(k))
            r[k] = en is not None and an is not None and abs(en - an) <= max(0.02, abs(en) * 0.01)
        elif k in ("vendor", "merchant"):
            ev = _norm(v)
            av = _norm(actual.get("vendor") or actual.get("merchant"))
            r[k] = bool(ev and av and (ev in av or av in ev))
        elif k == "currency":
            r[k] = _cur(v) == _cur(actual.get(k))
        else:
            r[k] = _norm(v) == _norm(actual.get(k))
    return r


def _imgs_for(row):
    if row.get("all_pages"):
        return [(BENCH / p).read_bytes() for p in row["all_pages"] if (BENCH / p).exists()]
    p = BENCH / row["file"]
    return [p.read_bytes()] if p.exists() else []


def _pdf_for(row) -> bytes:
    """Assemble this row's page image(s) into one in-memory PDF for upload to /extract,
    which takes a single file and does its own multi-page handling. A single-page doc still
    round-trips through PDF so the HTTP path is identical regardless of page count."""
    from PIL import Image
    imgs = [Image.open(io.BytesIO(b)).convert("RGB") for b in _imgs_for(row)]
    if not imgs:
        raise FileNotFoundError(row.get("file"))
    buf = io.BytesIO()
    imgs[0].save(buf, "PDF", save_all=True, append_images=imgs[1:])
    return buf.getvalue()


async def extract(route, row):
    imgs = _imgs_for(row)
    if not imgs:
        return {"error": "image_missing"}
    if route == "ocr_fallback":
        from services.llm_extractor import LLMExtractor
        from services.ocr_extractor import extract_text_from_image
        from core.config import settings
        text = "\n\f\n".join(extract_text_from_image(i) for i in imgs)
        if not text.strip():
            return {"error": "ocr_empty"}
        return await LLMExtractor(model=settings.LLM_CLEANUP).extract(text, row["doc_type"])
    from services.vision_extractor import extract_via_vision_llm
    if route in ("vision_route_b", "vision_local"):  # "vision_local" accepted for back-compat
        return await extract_via_vision_llm(imgs, doc_type=row["doc_type"], route_b=True)
    return await extract_via_vision_llm(imgs, doc_type=row["doc_type"])


async def extract_via_api(route, row, api_url, client):
    """Same contract as extract(), but through a real deployed instance's /extract endpoint
    instead of in-process service calls — see the module docstring's "Remote mode" section."""
    try:
        pdf = _pdf_for(row)
    except FileNotFoundError:
        return {"error": "image_missing"}
    resp = await client.post(
        f"{api_url}/extract",
        files={"file": (f"{row['doc_type']}.pdf", pdf, "application/pdf")},
        data={"route": route, "doc_type": row["doc_type"]},
    )
    if resp.status_code != 200:
        return {"error": f"http_{resp.status_code}: {resp.text[:200]}"}
    body = resp.json()
    fields = body.get("fields")
    return fields if isinstance(fields, dict) else {"error": body.get("error") or "no_fields"}


def ingest_ocr(row):
    """Free robustness probe: render + OCR (no LLM). Returns char count or raises."""
    from services.ocr_extractor import extract_text_from_image
    imgs = _imgs_for(row)
    if not imgs:
        raise FileNotFoundError(row["file"])
    return sum(len(extract_text_from_image(i)) for i in imgs)


async def ingest_ocr_via_api(row, api_url, client):
    """Same contract as ingest_ocr(), but through /extract/text?route=ocr on a real deployed
    instance — forces the OCR text-layer path (no LLM, no Marker) so the free robustness probe
    still means "ingest + OCR only" in remote mode."""
    pdf = _pdf_for(row)
    resp = await client.post(
        f"{api_url}/extract/text",
        files={"file": (f"{row['doc_type']}.pdf", pdf, "application/pdf")},
        data={"route": "ocr"},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"http_{resp.status_code}: {resp.text[:200]}")
    return len(resp.json().get("text") or "")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(BENCH / "ground_truth.jsonl"))
    ap.add_argument("--route", default=None)
    ap.add_argument("--scale-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--doc-type", default=None)
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--api-url", default=None,
                     help="Run against a real deployed instance's HTTP API instead of "
                          "in-process service calls (e.g. https://docintel-mm79.onrender.com). "
                          "See the module docstring's 'Remote mode' section.")
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.dataset) if l.strip()]
    if a.doc_type:
        rows = [r for r in rows if r["doc_type"] == a.doc_type]
    if a.limit:
        rows = rows[: a.limit]
    mode_label = f"{'scale-only' if a.scale_only else a.route}" + (f" via {a.api_url}" if a.api_url else " (in-process)")
    print(f"\nBenchmark: {len(rows)} docs | mode={mode_label}")

    t0 = time.time()
    ok = err = 0
    field_c = field_t = 0
    per_field: dict = {}
    per_type: dict = {}
    latencies: list = []   # per-document wall time (s) — real, not estimated
    total_cost = 0.0       # real $ from litellm.completion_cost(), summed across docs

    http_client = None
    if a.api_url:
        import httpx
        http_client = httpx.AsyncClient(timeout=300.0)

    if a.scale_only:
        sem = asyncio.Semaphore(a.concurrency)

        async def run_one(row):
            nonlocal ok, err
            async with sem:
                try:
                    if a.api_url:
                        await ingest_ocr_via_api(row, a.api_url, http_client)
                    else:
                        await asyncio.to_thread(ingest_ocr, row)
                    ok += 1
                except Exception:
                    err += 1
        await asyncio.gather(*(run_one(r) for r in rows))
    else:
        sem = asyncio.Semaphore(a.concurrency)

        async def run_one(row):
            nonlocal ok, err, field_c, field_t, total_cost
            async with sem:
                t_item = time.time()
                res = await (extract_via_api(a.route, row, a.api_url, http_client) if a.api_url
                             else extract(a.route, row))
                latencies.append(time.time() - t_item)
                if isinstance(res, dict):
                    total_cost += res.get("_cost_usd", 0.0) or 0.0
                pt = per_type.setdefault(row["doc_type"], [0, 0])
                if isinstance(res, dict) and "error" not in res:
                    ok += 1
                    pt[0] += 1
                else:
                    err += 1
                pt[1] += 1
                if row.get("expected") and isinstance(res, dict):
                    sc = score(row["doc_type"], row["expected"], res)
                    for k, val in sc.items():
                        field_c += int(val)
                        field_t += 1
                        pf = per_field.setdefault(k, [0, 0])
                        pf[0] += int(val)
                        pf[1] += 1
        await asyncio.gather(*(run_one(r) for r in rows))

    if http_client:
        await http_client.aclose()

    dt = time.time() - t0
    print(f"\n  processed: {ok + err}  ok: {ok}  errors: {err}  "
          f"success_rate: {ok / max(1, ok + err):.1%}")
    print(f"  wall: {dt:.1f}s  throughput: {(ok + err) / max(0.1, dt):.2f} docs/s "
          f"(concurrency={a.concurrency})")
    if not a.scale_only and latencies:
        latencies.sort()
        n = len(latencies)
        mean_lat = sum(latencies) / n
        p50 = latencies[n // 2]
        p95 = latencies[min(n - 1, int(n * 0.95))]
        print(f"  LATENCY (per doc, wall time): mean={mean_lat:.2f}s  p50={p50:.2f}s  p95={p95:.2f}s")
        print(f"  COST: total=${total_cost:.4f}  mean=${total_cost / n:.5f}/doc "
              f"(real, from litellm.completion_cost() — $0.00 for local/self-hosted Route B)")
    if not a.scale_only and field_t:
        print(f"  FIELD ACCURACY (GT subset): {field_c}/{field_t} = {field_c / field_t:.1%}")
        for k, (c, t) in sorted(per_field.items()):
            print(f"    {k:16} {c}/{t} = {c / max(1, t):.0%}")
        print("  by doc_type (ok/total):")
        for k, (c, t) in sorted(per_type.items()):
            print(f"    {k:16} {c}/{t}")


if __name__ == "__main__":
    asyncio.run(main())
