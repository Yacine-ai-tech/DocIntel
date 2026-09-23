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
| **B** — vision_route_b | Ollama qwen2.5-VL 7B (T4 GPU) | global + French/FCFA (106, 2026-09-22 rerun) | **97.8%** (405/414) — see note below |
| **C** — ocr_fallback | Surya OCR (GPU) + LLM cleanup | French/FCFA (50 docs, full sub-corpus) + global (fresh confirmation sample), GPU sessions (2026-09-22/23) | **96.3%** FCFA, **97.4%** global — see note below |

### Route B rerun, GPU-accelerated, with French/FCFA coverage (2026-09-22)

Route B was rerun on a GPU-accelerated instance (T4) against a 106-document sample: 6
invoices and 50 receipts from the global corpus (CORD-v2, invoice2data), plus a new
50-document French-language, West African CFA franc (FCFA/XOF) sub-corpus (25 invoices,
25 receipts) covering Senegal, Côte d'Ivoire, Mali, Bénin, Burkina Faso, Togo, and Niger
business documents.

| Metric | Result |
|---|---|
| Success rate | **106/106 (100%)** |
| Overall field accuracy | **97.8%** (405/414 fields) |
| Global sample (invoices + CORD-v2 receipts) | **89.9%** (80/89) |
| French/FCFA sample | **100%** (325/325) |

This is a substantial improvement over the prior baseline (64.1% invoices, 77.0%
receipts) and exceeds the target set for this route (>88.0% field accuracy). Two fixes
account for the change:

1. **Response length.** The local-inference token budget (`OLLAMA_NUM_PREDICT`) was 256
   tokens, insufficient for structured JSON output on any document with more than one or
   two line items, producing truncated/invalid JSON. Raised to 2048, matching the other
   vision route's budget.
2. **Image deskew.** Automatic rotation correction (Radon-transform-based skew detection)
   runs before tiling, improving the model's ability to read dense multi-column layouts —
   carried over from an earlier fix that had not yet been benchmarked against this route
   at scale.

Per-field accuracy on the full 106-document sample: currency, date, due date, merchant,
payment method, subtotal, and tax all scored 100%; invoice number and vendor scored 97%;
total scored 93%.

### Route C rerun, expanded 650-document corpus (2026-09-22 – 2026-09-23)

The corpus was expanded to 650 documents (6 invoices, 50 forms, ~544 CORD-v2 receipts,
and a 50-document French/FCFA West African sub-corpus). Three rounds of measurement were
run:

**Round 1 (Tesseract OCR, all 600 base documents).** Establishes a full-coverage
baseline. Real, but degraded by provider-side rate limiting on that day (212/600
documents exhausted their retry budget under sustained quota pressure and fell back to
regex-only extraction).

**Round 2 (Surya OCR, GPU-accelerated, initial fix).** A genuine root-cause fix — see
below — replaces Tesseract with a modern layout-aware OCR engine. An initial pass across
~200 documents (global + French/FCFA) measured 71.9% global / 51.1% FCFA field accuracy —
a large improvement over Round 1, but with FCFA trailing global. That gap was fully
diagnosed and closed in Round 3.

**Round 3 (Surya OCR + fixed fallback parser + provider-aware retry).** Root-caused the
gap: a second, independent defect in the regex-based fallback parser (used only when the
LLM cleanup call itself fails) truncated space-grouped thousands separators — the
convention used by FCFA/XOF and several other locales — at the first digit group. On a
rate-limited call this silently produced a wrong `total` (e.g. reading `3 278 040` as
`3.0`) and left every other field null. Fixed the parser, and separately fixed provider
rate-limit handling to retry against the request budget rather than degrading
immediately. Full, dedicated re-validation of the 50-document French/FCFA sub-corpus
after both fixes:

| Metric | FCFA sub-corpus (50/50 docs) |
|---|---|
| Field accuracy | **96.3%** (313/325) |
| Document-level fully-correct | **86.0%** (43/50) |
| Fallback-parser invocations | **0** |

A fresh confirmation sample on the global corpus after the same fixes scored **97.4%**
field accuracy with zero fallback-parser invocations, consistent with the FCFA result and
indicating the gap was the fallback-parser defect plus rate-limit handling, not an
OCR-quality or LLM-comprehension difference between document languages/locales.

**Root cause and fix (Surya wiring).** `services/surya_extractor.py` — the intended
first-choice OCR engine, with Tesseract as its fallback — had never actually run: it
parsed a `.text_lines` attribute that doesn't exist on the installed library's result
type, so every call silently returned empty text and fell through to Tesseract,
regardless of Surya's real capability. Fixed to parse the correct `.blocks` field
(verified directly: the model correctly read `TOTAL 40,000` against ground truth once
parsed correctly, where Tesseract had produced garbage or nothing on the same class of
image). Running it requires GPU (the installed library version's recognition step is a
foundation-model backend, not the classical CPU-viable version); validated on a Lightning
AI T4 instance.

Three further root causes were found and fixed in the Tesseract round:

1. **Preprocessing order.** OCR runs on the raw image first; CLAHE/Otsu enhancement is a
   fallback used only when the raw pass returns under 80 characters.
2. **Rate-limit handling.** The extractor honors the provider's stated retry-after window
   before degrading to regex-only extraction, instead of degrading immediately.
3. **Field disambiguation.** The cleanup prompt explicitly identifies the final amount due
   (never a subtotal, tax line, or cash/change amount) as `total`, with French invoice
   vocabulary (`Total TTC` vs `Total HT`) added for the FCFA corpus.

**Open items:**
- The full 650-document corpus has been validated in overlapping GPU sessions (the FCFA
  sub-corpus in full, global documents in multiple large samples), but not yet in one
  single, uninterrupted end-to-end pass — a fully powered single-run number over all 650
  remains the natural next step.
- Surya requires GPU to run at all (no viable CPU fallback in the currently installed
  version) — the hosted VPS demo instance runs Tesseract-only; Surya is available to
  anyone self-hosting with their own GPU, the same positioning as Route B's Ollama.

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

Extended from a single proof-of-concept document to a 50-document corpus (25 invoices, 25
receipts) spanning seven West African markets (Senegal, Côte d'Ivoire, Mali, Bénin,
Burkina Faso, Togo, Niger), with French field labels and FCFA formatting (space-grouped
thousands, no decimal subunit, 18% TVA):

| Route | Sample | Field Accuracy |
|---|---|---|
| A — Claude Sonnet 4.6 Vision | 1 document | 100% |
| B — Ollama qwen2.5-VL 7B (T4 GPU) | 50 documents | **100%** (325/325 fields) |
| C — Tesseract + LLM (fra+eng) | 50 documents | see Route C rerun above |

Route B's French/FCFA field accuracy is reported in full above (§ Route B rerun). Route A's
figure remains the original single-document proof of concept; extending it to the full
50-document sample is listed under Future Directions.

---

## Further Reading

- [`eval/BENCHMARK.md`](eval/BENCHMARK.md) — full methodology, corpus details, per-run results, honest caveats
- [`eval/SROIE_BENCHMARK.md`](eval/SROIE_BENCHMARK.md) — SROIE Task-3 deep-dive
- [`eval/EVAL_REAL.md`](eval/EVAL_REAL.md) — real invoice field-level breakdown
- [`RESEARCH.md`](RESEARCH.md) — why each architectural choice was made, and how DocIntel's numbers compare against independently published 2026 benchmarks
