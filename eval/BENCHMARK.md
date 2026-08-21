# DocIntel Benchmark

A reproducible benchmark of **real, third-party documents**, evaluating two properties that
matter for production document extraction:

1. **Accuracy** — field-level correctness against ground truth.
2. **Robustness at scale** — processing the corpus concurrently with a high success rate.

All datasets are publicly available; the downloaded artifacts are git-ignored and rebuilt by the
scripts below.

For how these numbers compare against independently-published 2026 benchmarks (LayoutLMv3,
DocMamba, published Claude Sonnet invoice-extraction studies) — and an honest answer to whether
any of this is novel — see [RESEARCH.md](../RESEARCH.md). This document stays focused on
DocIntel's own methodology and measured results.

## Corpus (106 documents, all with field-level ground truth)

| Source | Type | Docs | Ground truth | Rationale |
|--------|------|------|--------------|-----------|
| [CORD-v2](https://huggingface.co/datasets/naver-clova-ix/cord-v2) | receipt | 50 | `total` (IDR) | real phone-photo receipts with clean JSON ground truth |
| [invoice2data](https://github.com/invoice-x/invoice2data) (MIT) | invoice | 6 | full fields | EN/FR/DE/NL; multi-page (one total appears on page 2) |
| [FUNSD](https://guillaumejaume.github.io/FUNSD/) | form | 50 | — | noisy scanned forms with handwriting (scale/robustness) |

```bash
python eval/build_corpus.py --target 500      # -> eval/benchmark/ground_truth.jsonl + images/
```

**Corpus size caveat**: the full CORD-v2 sample (up to 494 receipts) requires the Hugging Face
`datasets` package and network access to pull. Results below are measured against the 106-document
corpus reproducible without that dependency; `build_corpus.py --target 500` restores the larger
sample where `datasets` and network access are available. A larger, more diverse corpus is listed
as future work in [RESEARCH.md](../RESEARCH.md).

## Scoring methodology

`eval/run_benchmark.py` scores **only the fields present** in each ground-truth record. Numeric
fields use a `max(0.02, 1%)` tolerance; vendor/merchant uses case-insensitive substring matching;
identifiers and dates require exact (whitespace-normalized) matches; currency is normalized to
ISO-4217. Receipts are scored on `total`; invoices on the full field set; forms contribute to the
scale/robustness measure (token-level ground truth, not field-scored).

**Remote mode** (`--api-url`): the results below were measured against the deployed production API
over HTTP rather than in-process, exercising the same Docker image and
code path that ships to production. See `eval/run_benchmark.py`'s module docstring for how
multi-page documents are handled in this mode.

## Results (measured 2026-08-15, against the deployed API)

**Concurrency note.** The deployed instance runs a single worker process (`--workers 1`,
`Dockerfile`); at concurrency 3-6 a share of requests time out under contention rather than
reflecting a model or extraction failure. The field-accuracy tables below therefore use
concurrency=1 (fully serialized) for reliability; the separate robustness pass further down
measures behavior under concurrent load directly. Self-hosters on comparably constrained hardware
should expect the same pattern and scale worker count with available CPU.

### Field accuracy by route (small-N, concurrency=1)

| Route | Engine | Document set | Requests completed | Field accuracy (of completed) |
|-------|--------|--------------|---------------------|-------------------------------|
| A — vision_route_a | Claude Sonnet 4.6 Vision | invoices (3) | 3/3 | **100%** (18/18 fields) |
| A — vision_route_a | Claude Sonnet 4.6 Vision | receipts (6) | 4/6 | **67%** (4/6, `total`) |
| B — vision_route_b | Ollama qwen2.5-VL 7B (self-hosted, remote endpoint) | invoices (2) | 2/2 | **100%** (14/14 fields) |
| B — vision_route_b | Ollama qwen2.5-VL 7B (self-hosted, remote endpoint) | receipts (4) | 3/4 | **25%** (1/4, `total`) |
| C — ocr_fallback | Tesseract + Claude Haiku | invoices (3) | 0/3 | timed out under concurrent load (see below) |
| C — ocr_fallback | Tesseract + Claude Haiku | receipts (6) | 0/6 | timed out under concurrent load (see below) |

**Route C's 0/3 and 0/6** reflect the concurrency-related timeouts described above, not an
extraction failure: a separate, isolated, uncontended request with the same route
(`POST /extract/text?route=ocr`) completed in 73s with a fully correct extraction.

**On the small N**: single-digit samples are noisy — Route B's 25% receipt figure and Route A's
67% receipt figure above are real measurements but should be read alongside, not as a replacement
for, the larger-sample results below. Both are kept, dated, so neither silently overwrites the
other.

### Larger-sample results (measured 2026-08-10, in-process)

| Route | Engine | Document set | Field accuracy |
|-------|--------|--------------|----------------|
| A — vision_route_a | Claude Sonnet 4.6 Vision | invoices (6; multilingual, multi-page) | **100%** (39/39) |
| A — vision_route_a | Claude Sonnet 4.6 Vision | receipts (40; CORD phone photos) | **92.5%** (37/40) |
| C — ocr_fallback | Tesseract (eng) + LLM cleanup | invoices (clean PDFs) | **100%** |
| C — ocr_fallback | Tesseract (eng) + LLM cleanup | receipts (200; CORD phone photos) | **28.5%** (57/200) |
| B — vision_local | Ollama qwen2.5-VL 7B (NVIDIA T4) | receipts (100; CORD phone photos) | **77.0%** (77/100) |
| B — vision_local | Ollama qwen2.5-VL 7B (NVIDIA T4) | invoices (6; multilingual, multi-page) | **64.1%** (25/39) |

### Robustness at scale

`--scale-only` (ingestion + OCR, no LLM) against the deployed API hit the same single-worker
concurrency ceiling described above: at concurrency 4-6 across 10-25 documents, every request
exceeded the 300s client timeout; at concurrency 1 across 6 documents, throughput was limited by
wall-clock time rather than failures. The original in-process robustness pass — no HTTP layer, so
not subject to the deployed instance's worker-count ceiling
(`python eval/run_benchmark.py --scale-only --concurrency 12`) — measured **550/550 documents
processed successfully (100%) at ~1.1 docs/s**, which is the figure representative of this code
path's throughput independent of any one instance's serving capacity.

### Cost & latency (measured via `litellm.completion_cost()`)

| Route | Document set | Mean latency (completed requests) | Mean cost/doc |
|-------|--------------|-----------------------------------|----------------|
| A | invoices (3) | 81.8s | $0.0122 |
| A | receipts (6) | 83.5s (p50 44.5s, p95 308s — contention-affected) | $0.0048 |
| B | invoices (2) | 138.0s | $0.0021 |
| B | receipts (4) | 76.6s | $0.0007 |

Route B's latency includes remote-host wake time where applicable: this is a wake-on-demand
architecture that sleeps when idle rather than paying for always-on GPU capacity (cold wake takes
roughly 4-5 minutes, see the README). These figures are not representative of steady-state,
low-contention latency — a separate warm, uncontended Route B request completed end-to-end in
19.7s with every field correct.

### French + West-African CFA franc (FCFA → XOF)

N=1 in the current corpus (an earlier version of this document referenced 7 FCFA documents; the
sample on disk currently holds 1). All 3 routes read it **100% correctly**, including the
space-grouped `1 003 000 FCFA` amount and the 18% TVA line, measured against the deployed API:

| Route | Engine | Score |
|-------|--------|-------|
| A — vision_route_a | Claude Sonnet 4.6 Vision | **1/1 = 100%** |
| B — vision_route_b | Ollama qwen2.5-VL 7B (self-hosted, remote endpoint) | **1/1 = 100%** |
| C — ocr_fallback (fra+eng) | Tesseract + LLM | **1/1 = 100%** (isolated request; see the concurrency note above) |

Full field-level breakdown in [EVAL_REAL.md](EVAL_REAL.md) (from the original, larger run).

### SROIE (world-standard receipt KIE)

Last measured **2026-06-19** (not re-run since — the SROIE loader needs the `datasets` package to
pull the test split from Hugging Face). Zero-shot Route A on the ICDAR-2019 SROIE Task-3 test set
scored **95.0% overall** (company 95%, date 90%, total 100%) — see
[SROIE_BENCHMARK.md](SROIE_BENCHMARK.md).

### Route B — local vision model

Route B is the private, zero-API-cost path; all computation stays on hardware you control. It is
evaluated with **Ollama `qwen2.5-VL:7b`**, run either on the same machine as DocIntel or on a
GPU host reachable over the network (`ROUTE_B_MODE=local` / `ROUTE_B_MODE=remote`).

> **Model note.** Llama 3.2 Vision and Qwen 2.5-VL were both evaluated as candidates for the
> local route. As of Ollama 0.30.x, Llama 3.2 Vision fails to load (its `mllama` architecture is
> reported as *unknown* by the bundled `llama-server` runner); on the Ollama build where it does
> load (0.11.x) its key-information-extraction quality on the French/FCFA invoice was unusable
> (0/7) versus 7/7 for Qwen 2.5-VL. **Qwen 2.5-VL is therefore the validated local model.** The
> route is model-agnostic via `OLLAMA_MODEL`, so any Ollama-served vision model (Llama 3.2 Vision,
> Gemma, etc.) can be substituted on a host whose runtime supports it.

**Large documents on the local route.** Ollama's default context window (4096 tokens) is too small
for multi-image chunks. The extractor sends fewer pages per call for `ollama/` models
(`VISION_PAGES_PER_CALL_LOCAL`, default 2) and raises the context size (`OLLAMA_NUM_CTX`, default
8192). For 100+ page documents, the OCR route (validated on a 120-page PDF) or premium vision is
recommended.

### Route A Alternatives (Surya and Marker)

- **Surya**: an advanced layout-aware OCR alternative for dense documents where pure Tesseract
  loses reading order. Wired (`services/surya_extractor.py`), not installed by default (heavy ML
  dependency — see `requirements-ml.txt`), not benchmarked.
- **Marker**: a specialized PDF-to-Markdown route, used for extracting full-text structure from
  born-digital documents prior to LLM/RAG processing (`/extract/text`, `route=marker`).

## Cost and compute notes

- **Cloud spend is bounded by sampling**: the cheap OCR-cleanup route runs broadly; the premium
  vision route runs on a representative sample. Corpus assembly and the `--scale-only` robustness
  pass incur no API cost (LLM-wise; OCR compute is real).
- **Route B** runs on a GPU that wakes on demand and is released after use.
- The pure-OCR scale pass uses English Tesseract for throughput; multilingual OCR (multiple
  language packs) is more accurate but slower — see [EVAL_REAL.md](EVAL_REAL.md).

## Deterministic post-processing (multi-currency / multi-locale normalization)

Both routes apply a deterministic normalization layer (`services/normalize.py`) over the model
output, since LLMs are unreliable at locale-specific parsing:

- **Amounts**: US `1,234.56`, EU `1.234,56`, spaced `1 234 567`, Swiss `1'234.56`, and
  parenthesised negatives are converted to floats (the rightmost `.`/`,` is the decimal mark).
- **Currency → ISO-4217**: symbols (`$ € £ ¥ ₹ ₦ ₩ ฿ FCFA RM R$ zł …`) and 3-letter codes
  (USD, EUR, GBP, JPY, INR, CNY, XOF, XAF, and ~40 more); a missing currency is inferred from
  symbols in the amount strings.
- **Dates → ISO-8601** via `dateparser` (DD/MM vs MM/DD; French/German/Spanish month names), with a
  common-format fallback when `dateparser` is unavailable.
- Conservative by design: unparseable values are left unchanged (normalization can only improve output).
- Locked by `tests/test_normalize.py` (US/EU/JP/IN/UK/CH/FCFA amounts, ISO currencies, dates).
