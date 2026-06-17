<!-- RESULT TABLES are filled from the live runs; see "Results" below. -->
# DocIntel Benchmark — 500+ real documents

A released, reproducible benchmark of **real, third-party documents** spanning multiple types,
languages, and structures — the research artifact called for in STRATEGY.md §3.9. It measures
two things that matter in production:

1. **Accuracy** — field-level correctness on the ground-truth subset.
2. **Robustness at scale** — processing the whole corpus concurrently with a high success rate.

## Corpus (550 documents, 500 with field ground truth)

| Source | Type | Docs | Ground truth | Why it's here |
|--------|------|------|--------------|---------------|
| [CORD-v2](https://huggingface.co/datasets/naver-clova-ix/cord-v2) | receipt | 494 | `total` (IDR) | scalable real receipts with clean JSON GT |
| [invoice2data](https://github.com/invoice-x/invoice2data) (MIT) | invoice | 6 | full fields | EN/FR/DE/NL, **multi-page** (QualityHosting total on p.2) |
| [FUNSD](https://guillaumejaume.github.io/FUNSD/) | form | 50 | — (scale/handwriting) | noisy scanned forms with **handwriting** |

Build it (downloads are free; artifacts are gitignored):

```bash
python eval/build_corpus.py --target 500      # → eval/benchmark/ground_truth.jsonl + images/
```

## Scoring

`eval/run_benchmark.py` scores **only the fields present** in each ground-truth row. Numbers use
a `max(0.02, 1%)` tolerance; vendor/merchant is lenient substring; ids/dates exact; currency is
ISO-normalized. Receipts are scored on `total`; invoices on the full field set; forms count
toward scale/robustness (token-level GT, not field-scored here).

## Results

### Robustness at scale (free — ingest + OCR, no LLM)

```bash
python eval/run_benchmark.py --scale-only --concurrency 12
```

<!--SCALE-->
Ingested + OCR'd **all 550 documents** (receipts, invoices, forms) with per-file error
isolation:

| Metric | Result |
|--------|--------|
| Documents processed | **550 / 550** |
| Success rate | **100.0%** (0 failures) |
| Errors | 0 |

Every document — clean PDF invoices, noisy phone-photo receipts, and scanned handwritten
forms — was ingested without a single crash or unhandled error. (This pass ran single-threaded
on a 4-core CPU box at ~1.1 docs/s; throughput scales with `--concurrency` and cores. The
number that matters here is the **0-failure success rate at scale**.)
<!--/SCALE-->

### Accuracy by route (ground-truth subset)

```bash
python eval/run_benchmark.py --route ocr_fallback   --doc-type receipt --limit 200   # Route C (Haiku)
python eval/run_benchmark.py --route ocr_fallback   --doc-type invoice                # Route C
python eval/run_benchmark.py --route vision_premium --doc-type receipt --limit 40     # Route A (Sonnet)
python eval/run_benchmark.py --route vision_premium --doc-type invoice                # Route A
python eval/run_benchmark.py --route vision_local   --doc-type receipt --limit 40     # Route B (Ollama, GPU)
```

<!--ACCURACY-->
| Route | Engine | Doc set | Field accuracy (GT subset) |
|-------|--------|---------|----------------------------|
| **A — vision_premium** | Claude Sonnet 4.6 Vision | invoices (6, multilingual, multi-page) | **39/39 = 100%** |
| **A — vision_premium** | Claude Sonnet 4.6 Vision | receipts (40, CORD phone photos) | **37/40 = 92.5%** |
| **C — ocr_fallback** | Tesseract (eng) + Claude Haiku | invoices (clean PDFs) | **100%** (see [EVAL_REAL.md](EVAL_REAL.md)) |
| **C — ocr_fallback** | Tesseract (eng) + Claude Haiku | receipts (200, CORD phone photos) | **57/200 = 28.5%** |
| **B — vision_local** | Ollama **qwen2.5vl:7b** (local, T4 GPU) | receipts (20, CORD phone photos) | **17/20 = 85.0%** |
| **B — vision_local** | Ollama **qwen2.5vl:7b** (local, T4 GPU) | invoices (6, multilingual, multi-page) | **25/39 = 64.1%** |
| **B — vision_local** | Ollama **qwen2.5vl:7b** (local, T4 GPU) | French + FCFA(XOF) sample | **7/7 = 100%** |

**Reading the numbers.** Vision-first (Route A) is strong everywhere: **100%** on real
multilingual, multi-page invoices (vendor, number, date, currency, subtotal, tax, total — incl.
a total that only appears on page 2) and **92.5%** on hard, real-world *phone-photo* receipts.
The pure-OCR fallback (Route C) is excellent on clean documents (100% on invoices) but drops to
**28.5%** on noisy CORD phone receipts — Tesseract loses too much on crumpled thermal paper and
the Indonesian rupiah's `.`-as-thousands format. **This contrast is the whole thesis of the
project**: lead with the vision LLM, keep OCR as a cheap fallback for clean inputs. (Route A
receipts were run at `--concurrency 1` to stay under the Anthropic tier-1 limit of 30k input
tokens/min; at higher concurrency on tier-1 you will see `RateLimitError`s.)

### French + West-African CFA franc (FCFA → XOF)

A reproducible French invoice priced in FCFA (UEMOA-style, 18% TVA, space-grouped amounts) is
read **100% correctly by both routes** — full breakdown in [EVAL_REAL.md](EVAL_REAL.md):

| Route | Engine | Score |
|-------|--------|-------|
| A — vision_premium | Claude Sonnet 4.6 Vision | **7/7 = 100%** |
| C — ocr_fallback (fra+eng) | Tesseract + Claude Haiku | **7/7 = 100%** |

### Route B (Ollama local vision) — validated on a T4 GPU

Route B is the **private, zero-API-cost** path (everything stays on the box). Validated with
**Ollama `qwen2.5vl:7b` on a Lightning T4** (the pitch model `llama3.2-vision` is blocked by a
`mllama` runner bug in the available Ollama 0.30.8, so we use Qwen2.5-VL — also Ollama, and
listed in STRATEGY §3.10):

- **Receipts (CORD phone photos): 17/20 = 85%** — far above the pure-OCR fallback (28.5%) and
  approaching premium Claude Vision (92.5%), at **$0 per page**.
- **French + FCFA(XOF): 7/7 = 100%.**
- Invoices (multilingual, multi-page): 25/39 = 64% (a 7B local model trails Claude on the
  hardest layouts — the expected premium-vs-local tradeoff).

**Large docs on the local route:** Ollama's default context is 4096 tokens, too small for
multi-image chunks. The extractor now sends fewer pages per call for `ollama/` models
(`VISION_PAGES_PER_CALL_LOCAL`, default 2) and raises `num_ctx` (`OLLAMA_NUM_CTX`, default
8192). For 100+ page documents the OCR route (Route C, validated 7/7 on a 120-page PDF) or
premium vision is recommended.

Reproduce: `ollama pull qwen2.5vl:7b && LLM_VISION_LOCAL=ollama/qwen2.5vl:7b python eval/run_benchmark.py --route vision_local --doc-type receipt --limit 20`
<!--/ACCURACY-->

## Cost & compute notes

- **Anthropic spend is bounded by sampling**: Route C (cheap Haiku cleanup) runs broad; Route A
  (Sonnet Vision) runs on a representative sample. The corpus assembly and the `--scale-only`
  robustness pass cost nothing.
- **Route B (Ollama Llama-3.2-Vision)** runs on a Lightning GPU attached on-demand via
  `scripts/gpu_activate.py` and released immediately after, to conserve free GPU-hours.
- The pure-OCR scale pass uses English Tesseract for throughput; multilingual OCR (6 packs) is
  more accurate but slower — see [EVAL_REAL.md](EVAL_REAL.md) for the multilingual accuracy run.

## Update — Route B at larger N + SROIE (2026-06-17, T4 GPU)
- **Route B (Ollama qwen2.5vl) on 100 CORD receipts**: **77.0% total accuracy** (100/100 processed,
  0 errors) — the credible larger-N number (the earlier 85% was N=20). Still beats Route C (28.5%),
  below Route A (92.5%) — the expected premium-vs-local-7B tradeoff, at **$0/page**.
- **SROIE** (world-standard receipt KIE, zero-shot Route A): **95% overall** — see SROIE_BENCHMARK.md.
- `llama3.2-vision` — full investigation (CPU, no GPU billing): the `unknown model
  architecture: 'mllama'` failure is **Ollama-version-specific** (fails to load on 0.4.7 /
  0.5.13 / 0.6.8 / 0.30.8; **loads fine on Ollama 0.11.4** — verified "PONG"). But once
  loaded, its *extraction quality* is the blocker: on the French + FCFA invoice it scored
  **0/7** vs qwen2.5vl's 7/7. So the conclusion is unchanged but for the honest reason —
  not "can't load" but "loads (on 0.11.4) yet its KIE output is unusable". **qwen2.5vl is
  the Route B model** (also Ollama, STRATEGY §3.10 sanctioned alternate).

## Multi-currency / multi-locale normalization (2026-06-17)
Beyond FCFA, both routes now run a **deterministic post-processing layer**
(`services/normalize.py`) over LLM output — the hybrid step STRATEGY §3.4 / Day 36 calls for,
since LLMs are unreliable at locale-specific parsing:
- **Amounts**: US `1,234.56`, EU `1.234,56`, spaced `1 234 567`, Swiss `1'234.56`,
  parenthesised negatives → float (rightmost of `.`/`,` is the decimal mark).
- **Currency → ISO 4217**: `$`/`€`/`£`/`¥`/`₹`/`₦`/`₩`/`฿`/`FCFA`/`RM`/`R$`/`zł`/… and 3-letter
  codes (USD, EUR, GBP, JPY, INR, CNY, XOF, XAF + ~40 more); a missing `currency` is inferred
  from symbols seen in the amount strings.
- **Dates → ISO 8601** via `dateparser` (DD/MM vs MM/DD, French/German/Spanish month names),
  with a common-format fallback when dateparser is absent.
- Conservative: unparseable values are left untouched (can only improve LLM output).
- Locked by `tests/test_normalize.py` (US/EU/JP/IN/UK/CH/FCFA amounts, ISO currencies, dates).
