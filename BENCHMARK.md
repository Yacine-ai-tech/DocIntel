# Benchmark Results

This document provides a headline summary of DocIntel's measured extraction accuracy,
robustness, cost, and latency. All methodology details, per-run corpus composition, and
scoring rules are in [`eval/BENCHMARK.md`](eval/BENCHMARK.md) — that file is the single
source of truth; this one is the entry point.

> **Infrastructure note.** The deployed instance runs a **single worker process** on a
> free-tier host. At concurrency ≥ 3 some requests time out — those are infrastructure
> ceiling numbers, not extraction failures. In-process runs (no HTTP layer, no worker
> ceiling) are labelled separately below and reflect the code's actual throughput.

---

## Field Accuracy by Route

Measured against real, third-party documents (CORD-v2 receipts, invoice2data invoices,
SROIE receipts). Full corpus composition and scoring rules: [`eval/BENCHMARK.md`](eval/BENCHMARK.md).

### Larger-sample results (in-process, 2026-08-10)

| Route | Engine | Document set | Field accuracy |
|---|---|---|---|
| **A** — vision_route_a | Claude Sonnet 4.6 Vision | invoices (6, multilingual, multi-page) | **100%** (39/39 fields) |
| **A** — vision_route_a | Claude Sonnet 4.6 Vision | receipts (40, CORD phone photos) | **92.5%** (37/40) |
| **B** — vision_route_b | Ollama qwen2.5-VL 7B (T4 GPU) | receipts (100, CORD phone photos) | **77.0%** (77/100) |
| **B** — vision_route_b | Ollama qwen2.5-VL 7B (T4 GPU) | invoices (6, multilingual, multi-page) | **64.1%** (25/39) |
| **C** — ocr_fallback | Tesseract + LLM cleanup | invoices (clean PDFs) | **100%** |
| **C** — ocr_fallback | Tesseract + LLM cleanup | receipts (200, CORD phone photos) | **28.5%** (57/200) |

### SROIE (world-standard receipt KIE benchmark, 2026-06-19)

Zero-shot Route A on the ICDAR-2019 SROIE Task-3 test set:

| Metric | Score |
|---|---|
| Overall | **95.0%** |
| Company | 95% |
| Date | 90% |
| Total | 100% |

Full details: [`eval/SROIE_BENCHMARK.md`](eval/SROIE_BENCHMARK.md).

---

## Robustness at Scale

| Mode | Concurrency | Documents | Success rate | Throughput |
|---|---|---|---|---|
| In-process (no HTTP layer) | 12 | 550 | **100%** | **~1.1 docs/s** |
| Deployed API (single worker) | 4–6 | 10–25 | 0% — timeout | n/a (ceiling hit) |

The deployed-API row reflects the **single-worker free-tier ceiling**, not a code bug.
Scale worker count with available CPU to raise concurrency capacity.

---

## Cost & Latency (deployed API, 2026-08-15)

| Route | Document set | Mean latency | Mean cost/doc |
|---|---|---|---|
| A | invoices (3) | 81.8 s | $0.0122 |
| A | receipts (6) | 83.5 s (contention-affected) | $0.0048 |
| B | invoices (2) | 138.0 s (includes GPU cold-wake) | $0.0021 |
| B | receipts (4) | 76.6 s | $0.0007 |

Route B latency includes **GPU host cold-wake time (~4–5 min on first request after idle)**
— a deliberate cost tradeoff (zero always-on GPU spend). A warm, uncontended Route B
request completes end-to-end in **19.7 s**.

---

## French / West-African CFA franc (FCFA → XOF)

All three routes read the FCFA sample correctly, including space-grouped amounts and TVA:

| Route | Score |
|---|---|
| A — Claude Sonnet 4.6 Vision | **1/1 = 100%** |
| B — Ollama qwen2.5-VL 7B (remote) | **1/1 = 100%** |
| C — Tesseract + LLM (fra+eng) | **1/1 = 100%** |

---

## Further Reading

- [`eval/BENCHMARK.md`](eval/BENCHMARK.md) — full methodology, corpus details, per-run results, honest caveats
- [`eval/SROIE_BENCHMARK.md`](eval/SROIE_BENCHMARK.md) — SROIE Task-3 deep-dive
- [`eval/EVAL_REAL.md`](eval/EVAL_REAL.md) — real invoice field-level breakdown
- [`RESEARCH.md`](RESEARCH.md) — why each architectural choice was made, and how DocIntel's numbers compare against independently published 2026 benchmarks
