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
| **C** — ocr_fallback | Tesseract + LLM cleanup | global + French/FCFA, 333/600 processed (2026-09-22, in progress) | **33.5%** (106/316) — see note below |

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

### Route C rerun, expanded 600-document corpus (2026-09-22, in progress)

The corpus was expanded to 600 documents (6 invoices, 50 forms, 494 CORD-v2 receipts, and
a new 50-document French/FCFA West African sub-corpus). Route C was rerun end to end
in-process, using rotation across three independent API accounts to sustain throughput
against per-account daily token quotas.

| Metric | Prior rerun (550 docs) | Current rerun (333/600, in progress) |
|---|---|---|
| Images where OCR returned no text | 245 / 550 (44.5%) | 44 / 333 (13.2%), consistent |
| Overall field accuracy | 22.7% (121/533) | **33.5%** (106/316) |
| Field accuracy, OCR-readable documents | 26.3% | **39.0%** (106/272) |

Four root causes have been found and fixed across this and the prior rerun:

1. **Preprocessing order.** OCR now runs on the raw image first; CLAHE/Otsu enhancement is
   a fallback used only when the raw pass returns under 80 characters — reduced the
   empty-OCR rate from 44.5% to ~13%, holding steady in this rerun.
2. **Rate-limit handling.** The extractor now honors the provider's stated retry-after
   window before degrading to regex-only extraction, instead of degrading immediately.
3. **Numeric locale.** Dot-grouped integers (e.g. Indonesian Rupiah `31.000`) are now
   distinguished from decimals during normalization.
4. **Field disambiguation.** The cleanup prompt now explicitly identifies the final
   amount due (never a subtotal, tax line, or cash/change amount) as `total`, with French
   invoice vocabulary (`Total TTC` vs `Total HT`) added for the new FCFA corpus. This
   accounts for the accuracy gain in the current rerun.

**Status:** this rerun is running against a real, enforced constraint — each of the three
rotation accounts has a per-day token quota (not just per-minute), and all three were
exhausted before the corpus's French/FCFA slice (positioned last in the corpus) was
reached. The remaining ~267 documents, including the full FCFA slice, will complete once
quotas reset; this document will be updated with the final, complete numbers at that
point.

**Open items:**
- The 6 invoices scored 56.4% (22/39 fields) in the prior full-corpus rerun, below the
  original 100% figure measured on a different input form; needs investigation once the
  full rerun completes.
- Some receipts remain permanently unreadable: very dark, low-dynamic-range phone photos
  that Tesseract cannot recover even after enhancement (§ Route B above handles these
  documents via vision extraction instead).

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
