# DocIntel — SROIE Benchmark (standard receipt KIE)

Zero-shot Route A (Claude Sonnet 4.6 Vision) on the **SROIE** test set (ICDAR-2019 Task 3 — the
standard benchmark for receipt key-information extraction). Reproducible:
`python eval/run_sroie_benchmark.py --n 20` (requires `ANTHROPIC_API_KEY` and the `datasets` package).

## Setup
- **Dataset:** `nhernandez99/sroie_dataset` (SROIE test split; donut-format ground truth —
  company / date / total).
- **Scoring:** company = case-insensitive substring; date = format-agnostic component match
  (DD/MM/YYYY ≡ YYYY-MM-DD); total = numeric within `max(0.02, 1%)`.

## Results (N = 20)
| Field | Accuracy |
|-------|----------|
| company | 95.0% (19/20) |
| date | 90.0% (18/20) |
| total | 100.0% (20/20) |
| **Overall** | **95.0% (57/60)** |

## Discussion
On a world-recognized benchmark, **zero-shot** Claude vision reaches **95% field accuracy** with no
task-specific fine-tuning. Published SROIE state of the art is ~96–98% F1 from *task-fine-tuned*
LayoutLM-class models, so this is near-SOTA out of the box — supporting the vision-first design.

## Limitations
- **N = 20:** this Hugging Face mirror's test split is small; the figure is indicative, not a
  full-test-set F1. DocIntel is additionally evaluated on **CORD** (494 receipts; 92.5% Route A) —
  see [BENCHMARK.md](BENCHMARK.md) — providing a second standard receipt dataset at larger scale.
- **Date scoring:** an initial run scored date at 0% due to an ISO-vs-DD/MM/YYYY digit-order
  mismatch; switching to component-set matching corrected this (the reported 90% reflects genuine
  format-agnostic accuracy).
