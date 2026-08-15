# DocIntel: Vision-LLM-First Document Extraction

## What this actually is

DocIntel extracts structured data from documents (invoices, receipts, contracts, forms,
financial reports) using a **vision-LLM-first** approach: page images go directly to a
vision-capable LLM, which returns structured JSON — no OCR text layer in between. This is the
2026 shift the project is built around (see `global_docs/STRATEGY.md` §3.10): pure-OCR pipelines
throw away layout, table structure, and handwriting the moment they flatten a page into a string
of characters; a vision model reasons over the page image itself.

Three extraction routes, chosen per-request or via env default:

- **Route A** — Claude Sonnet 4.6 Vision (cloud, metered, real per-call cost tracked via
  `litellm.completion_cost()`).
- **Route B** — Ollama vision (Qwen 2.5-VL 7B validated; see `eval/BENCHMARK.md` for why Llama
  3.2 Vision was tried and rejected), run either on the same machine/LAN or on hardware you
  control elsewhere — never a third-party inference API. $0 per call.
- **Route C** — Tesseract OCR + LLM cleanup, the fallback for when vision-LLM cost is
  prohibitive or image quality is too low for a vision model to help (very low-res scans, faxes).
  Also the automatic fallback if Route A/B fails.

Multi-page documents (up to `MAX_PDF_PAGES`, default 200) are handled by chunking pages across
multiple vision calls and merging results (`services/doc_merge.py`): list fields concatenate
across chunks, running-total-style fields take the last non-empty chunk, everything else takes
the first non-null value seen.

## Deterministic post-processing

LLMs are unreliable at locale-specific formatting, so amounts, currencies, and dates go through
a deterministic normalization layer (`services/normalize.py`) after extraction, not instead of
it — the model still reads the document; this layer only standardizes how the answer is
represented:

- **Amounts**: US `1,234.56`, EU `1.234,56`, space-grouped `1 234 567`, Swiss `1'234.56`, and
  parenthesised negatives all convert to a plain float — conservatively: a value that doesn't
  match a known pattern is left unchanged rather than guessed at.
- **Currency → ISO-4217**: symbols and codes for ~40+ currencies, including West/Central African
  CFA franc (`FCFA`/`CFA` → `XOF` or `XAF` depending on context) — a currency STRATEGY.md's
  original v1 design didn't cover and general-purpose LLM normalization gets wrong by default.
- **Dates → ISO-8601** via `dateparser`, with a common-format fallback when it's unavailable.

Locked by `tests/test_normalize.py` (US/EU/JP/IN/UK/CH/FCFA amounts, ISO currencies, dates).

## What is NOT built (said plainly, not glossed over)

- **No layout/structure model.** DocIntel does not build a bounding-box graph, reading-order
  edges, or a layout tree of any kind. A prior version of this document claimed otherwise
  (a "$\mathcal{T}_{layout}=(V,E)$ spatial layout tree" formalism) — that description didn't
  correspond to any code that exists in this repo and has been removed. The only real per-element
  bounding-box output anywhere in the codebase is Surya OCR's flat per-line `bbox` list
  (`services/surya_extractor.py`, an optional fallback path, not installed by default) and
  pdfplumber's per-table bbox from `/extract-tables` — neither is a graph, neither has edges,
  and neither feeds into extraction quality; they're incidental output of two specific routes.
- **No table-structure F1 / layout-hierarchy / character-error-rate benchmark.** What's measured
  (below) is field-level extraction accuracy: did the model get the vendor, total, date, line
  items right. That's a different, real, and directly useful metric — it is not layout precision
  or CER, and this document previously implied numbers existed for the latter that never did.

## Real, reproducible results

Full methodology, corpus composition, and scoring rules: [eval/BENCHMARK.md](eval/BENCHMARK.md).
Reproducible via `python eval/build_corpus.py` + `python eval/run_benchmark.py`, and the same
numbers are served live (so this document and the running app can't silently diverge) via
`GET /benchmarks`. See BENCHMARK.md for the current corpus size and per-route numbers — this
document doesn't duplicate them so there's exactly one place they can go stale.

## Citation

```bibtex
@techreport{siddo2026docintel,
  author      = {Yacine Seybou Siddo},
  title       = {DocIntel: Vision-LLM-First Document Extraction},
  institution = {GitHub Repository},
  year        = {2026},
  url         = {https://github.com/Yacine-ai-tech/DocIntel}
}
```
