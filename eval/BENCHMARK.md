# DocIntel Benchmark

A reproducible benchmark of **real and structured third-party documents across 650 documents**, evaluating two properties that matter for production document extraction:

1. **Accuracy** — field-level correctness against ground truth.
2. **Robustness at scale** — processing the corpus concurrently with a high success rate.

All datasets are publicly available or deterministically generated; downloaded artifacts are git-ignored and rebuilt by the scripts in `eval/`.

For how these numbers compare against independently-published 2026 benchmarks (LayoutLMv3,
DocMamba, published Claude Sonnet invoice-extraction studies) — and an honest answer to whether
any of this is novel — see [RESEARCH.md](../RESEARCH.md). This document stays focused on
DocIntel's own methodology and measured results.

## Corpus (650 documents across multi-format, multilingual sources)

| Source | Type | Docs | Ground truth | Rationale |
|--------|------|------|--------------|-----------|
| [CORD-v2](https://huggingface.co/datasets/naver-clova-ix/cord-v2) | receipt | ~544 | `total` (IDR) | real phone-photo receipts with clean JSON ground truth |
| [invoice2data](https://github.com/invoice-x/invoice2data) (MIT) | invoice | 6 | full fields | EN/FR/DE/NL; multi-page (one total appears on page 2) |
| [FUNSD](https://guillaumejaume.github.io/FUNSD/) | form | 50 | — | noisy scanned forms with handwriting (scale/robustness) |
| French / FCFA sub-corpus (UEMOA 18% TVA) | invoice/receipt | 50 | full fields | 25 invoices + 25 receipts spanning 7 West-African countries |

```bash
python eval/build_corpus.py --target 600      # -> eval/benchmark/ground_truth.jsonl + images/
```

**Corpus composition**: The full multi-source corpus assembles 650 documents: 6 multilingual invoices,
50 forms, ~544 CORD-v2 receipts, and 50 West-African French/FCFA invoices and receipts. For offline
or minimal-dependency runs, a 106-document reproducible baseline (56 global + 50 FCFA) is evaluated,
while `build_corpus.py --target 600` pulls the complete 650-document dataset when the `datasets`
package and network access are available.

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

## Comprehensive Benchmark Results

### 1. Field Accuracy by Route

| Route | Engine | Document set | Field accuracy |
|---|---|---|---|
| **A** — vision_route_a | Claude Sonnet 4.6 Vision | Multilingual invoices, multi-page (39 fields) | **100%** |
| **A** — vision_route_a | Claude Sonnet 4.6 Vision | CORD receipts, phone photographs (40 documents) | **92.5%** |
| **A** — vision_route_a | Claude Sonnet 4.6 Vision | SROIE receipts (ICDAR-2019 Task 3) | **95.0%** |
| **B** — vision_route_b | Ollama Qwen 2.5-VL 7B (self-hosted, GPU) | Global sample (invoices + CORD receipts) | **89.9%** |
| **B** — vision_route_b | Ollama Qwen 2.5-VL 7B (self-hosted, GPU) | French / FCFA sample (50 documents) | **100%** |
| **B** — vision_route_b | Ollama Qwen 2.5-VL 7B (self-hosted, GPU) | Combined 106-doc sample (405/414 fields) | **97.8%** |
| **C** — ocr_fallback | Surya OCR (GPU) + LLM cleanup | French / FCFA sub-corpus (50 documents) | **96.3%** |
| **C** — ocr_fallback | Surya OCR (GPU) + LLM cleanup | Global sample | **97.4%** |

### 2. French / West-African CFA Franc (FCFA → XOF)

Evaluated on the 50-document sub-corpus (25 invoices, 25 receipts) spanning Senegal, Côte d'Ivoire,
Mali, Bénin, Burkina Faso, Togo, and Niger with space-grouped thousands, 18% TVA, and ISO-4217
normalization (`services/normalize.py`):

| Route | Engine | Sample size | Field accuracy |
|---|---|---|---|
| A — vision_route_a | Claude Sonnet 4.6 Vision | 1 document | **100%** (proof of concept) |
| B — vision_route_b | Ollama Qwen 2.5-VL 7B (GPU) | 50 documents | **100%** (325/325 fields) |
| C — ocr_fallback | Surya OCR (GPU) + LLM cleanup | 50 documents | **96.3%** (313/325 fields) |

### 3. Robustness at Scale

| Mode | Concurrency | Documents | Success rate | Throughput |
|---|---|---|---|---|
| In-process | 12 | 550–650 | **100%** (0 unhandled errors) | ~1.1 docs/s |

Ingestion and OCR scale pass measures pipeline resilience directly under concurrent execution,
verifying deduplication and memory stability across all document formats.

### 4. Cost & Latency (measured via `litellm.completion_cost()`)

| Route | Document set | Mean latency (completed requests) | Mean cost/doc |
|---|---|---|---|
| A | invoices (3) | 81.8s | $0.0122 |
| A | receipts (6) | 83.5s (p50 44.5s) | $0.0048 |
| B | invoices (2) | 138.0s (includes GPU wake) | $0.0021 |
| B | receipts (4) | 76.6s | $0.0007 |

Route B's latency includes wake-on-demand GPU boot overhead. Steady-state, uncontended Route B requests
complete in **19.7s** with zero third-party API spend ($0.00).

### 5. Historical Route C Baseline (Tesseract-Only Fallback)

For environments running without a GPU where Surya OCR cannot be loaded, Route C automatically
falls back to Tesseract OCR:

| Route | Engine | Document set | Field accuracy |
|---|---|---|---|
| C (fallback) | Tesseract (eng) + LLM cleanup | Clean PDF invoices | **100%** |
| C (fallback) | Tesseract (eng) + LLM cleanup | CORD phone receipts (200 docs) | **28.5%** (57/200) |

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

### Route C's OCR Engine (Surya, primary) and Marker

- **Surya**: a layout-aware OCR engine that is Route C's **default, primary** OCR engine
  (`services/surya_extractor.py`) — Tesseract is retained only as the automatic fallback
  when Surya is unavailable (it requires a GPU; no CPU-viable path in the currently
  installed version) or returns empty text. Surya is heavily benchmarked at the top-level
  [`BENCHMARK.md`](../BENCHMARK.md)'s Route C section, including a full French/FCFA
  sub-corpus rerun; not installed by default in a CPU-only environment (heavy ML
  dependency — see `requirements-ml.txt`).
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
