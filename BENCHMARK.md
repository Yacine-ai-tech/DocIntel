# Benchmark Results

This document reports DocIntel's measured extraction accuracy, throughput, and cost across
its three extraction routes, against real, third-party document corpora. Full methodology,
per-run corpus composition, and scoring rules are in [`eval/BENCHMARK.md`](eval/BENCHMARK.md);
this document is a summary entry point.

---

## Field Accuracy by Route

Measured against real, third-party documents drawn from CORD-v2 (receipts), `invoice2data`
(invoices), and SROIE (ICDAR-2019 Task 3 receipts).

| Route | Engine | Document set | Field accuracy |
|---|---|---|---|
| **A** — vision_route_a | Claude Sonnet 4.6 Vision | Multilingual invoices, multi-page (39 fields) | **100%** |
| **A** — vision_route_a | Claude Sonnet 4.6 Vision | CORD receipts, phone photographs (40 documents) | **92.5%** |
| **A** — vision_route_a | Claude Sonnet 4.6 Vision | SROIE receipts | **95.0%** |
| **B** — vision_route_b | Ollama Qwen 2.5-VL 7B (self-hosted, GPU) | Global + French/FCFA sample, 106 documents | **97.8%** |
| **C** — ocr_fallback | Surya OCR (GPU) + LLM cleanup | French/FCFA sub-corpus, 50 documents | **96.3%** |
| **C** — ocr_fallback | Surya OCR (GPU) + LLM cleanup | Global sample | **97.4%** |

### Route B — Qwen 2.5-VL 7B, GPU-accelerated

Measured on a 106-document sample: 56 documents from the global corpus (CORD-v2, `invoice2data`)
and a 50-document French-language corpus in the West African CFA franc (FCFA/XOF) format,
spanning invoices and receipts from Senegal, Côte d'Ivoire, Mali, Bénin, Burkina Faso, Togo,
and Niger.

| Metric | Result |
|---|---|
| Success rate | 106/106 (100%) |
| Overall field accuracy | 97.8% (405/414 fields) |
| Global sample | 89.9% (80/89) |
| French/FCFA sample | 100% (325/325) |

Per-field accuracy on the full sample: currency, date, due date, merchant, payment method,
subtotal, and tax each scored 100%; invoice number and vendor scored 97%; total scored 93%.

Two factors account for Route B's result relative to an earlier, lower-accuracy configuration:
a local-inference token budget that had been insufficient for structured JSON output on
multi-line-item documents (raised to match Route A's budget), and automatic rotation
correction (Radon-transform-based skew detection) applied before tiling, which improves
reading of dense multi-column layouts.

Note: Llama 3.2 Vision 11B was evaluated as a candidate model for this route and is not used
— it fails to load on current Ollama builds, or scores near zero on builds where it does load.
Qwen 2.5-VL 7B is the validated model for Route B.

### Route C — Surya OCR with Tesseract fallback

The corpus for this route comprises 650 documents: 6 invoices, 50 forms, approximately 544
CORD-v2 receipts, and the 50-document French/FCFA sub-corpus described above.

| Metric | FCFA sub-corpus (50 documents) |
|---|---|
| Field accuracy | **96.3%** (313/325) |
| Fully correct at document level | 86.0% (43/50) |

A confirmation run on the global corpus, under the same configuration, scored **97.4%** field
accuracy, indicating the accuracy level is consistent across languages and locales rather than
specific to either sample.

Surya OCR (layout-aware, requiring a GPU) is the primary engine for this route; Tesseract is
the automatic fallback on systems without a GPU or when Surya returns no text. Three factors
contribute to Route C's measured accuracy:

1. **Preprocessing order** — OCR is run on the raw image first, with CLAHE/Otsu contrast
   enhancement applied only as a fallback for low-text-yield passes.
2. **Provider-side rate-limit handling** — the extractor honors a provider's stated retry
   window before falling back to regex-only extraction, rather than degrading immediately.
3. **Field disambiguation** — the LLM cleanup prompt explicitly identifies the final amount
   due (as distinct from a subtotal, tax line, or change amount) as the `total` field, with
   French invoice vocabulary (`Total TTC` vs. `Total HT`) covered for the FCFA corpus.

**Scope note.** Surya OCR requires a GPU to run; deployments without one use the Tesseract
fallback, at lower accuracy (see the earlier Route C baseline in
[`eval/BENCHMARK.md`](eval/BENCHMARK.md) for the Tesseract-only figures). This mirrors Route
B's positioning: the GPU-accelerated path is available to any self-hosted deployment with
GPU access.

### SROIE (ICDAR-2019 Task 3)

Zero-shot Route A on the SROIE receipt key-information-extraction test set:

| Metric | Score |
|---|---|
| Overall | **95.0%** |
| Company | 95% |
| Date | 90% |
| Total | 100% |

Full detail: [`eval/SROIE_BENCHMARK.md`](eval/SROIE_BENCHMARK.md).

---

## Throughput at Scale

| Mode | Concurrency | Documents | Success rate | Throughput |
|---|---|---|---|---|
| In-process | 12 | 550 | 100% | ~1.1 docs/s |

In-process figures measure the extraction pipeline directly, independent of any particular
deployment's request-handling configuration.

---

## Cost and Latency

| Route | Document set | Mean latency | Mean cost per document |
|---|---|---|---|
| A | Invoices | 81.8 s | $0.0122 |
| A | Receipts | 83.5 s | $0.0048 |
| B | Invoices | 138.0 s (includes GPU wake) | $0.0021 |
| B | Receipts | 76.6 s | $0.0007 |

Route B's latency figures include cold-start time for the self-hosted GPU host (a deliberate
cost tradeoff against running a GPU continuously). A warm, uncontended Route B request
completes end-to-end in 19.7 s.

---

## French / West African CFA Franc (FCFA → XOF)

A 50-document corpus (25 invoices, 25 receipts) spanning seven West African markets (Senegal,
Côte d'Ivoire, Mali, Bénin, Burkina Faso, Togo, Niger), with French field labels and FCFA
formatting (space-grouped thousands, no decimal subunit, 18% TVA):

| Route | Sample size | Field accuracy |
|---|---|---|
| A — Claude Sonnet 4.6 Vision | 1 document | 100% |
| B — Ollama Qwen 2.5-VL 7B (GPU) | 50 documents | **100%** (325/325) |
| C — Surya OCR + LLM cleanup | 50 documents | **96.3%** (313/325) |

Route A's figure is a single-document proof of concept; extending it to the full 50-document
sample is listed under Future Directions in [RESEARCH.md](RESEARCH.md).

---

## Further Reading

- [`eval/BENCHMARK.md`](eval/BENCHMARK.md) — full methodology, corpus composition, and reproduction steps
- [`eval/SROIE_BENCHMARK.md`](eval/SROIE_BENCHMARK.md) — SROIE Task-3 detail
- [`eval/EVAL_REAL.md`](eval/EVAL_REAL.md) — real-invoice field-level breakdown
- [`RESEARCH.md`](RESEARCH.md) — architectural rationale and comparison against independently published 2026 benchmarks
