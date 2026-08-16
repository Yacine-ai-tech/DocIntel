# DocIntel: Vision-LLM-First Document Extraction

## What this actually is

DocIntel extracts structured data from documents (invoices, receipts, contracts, forms,
financial reports) using a **vision-LLM-first** approach: page images go directly to a
vision-capable LLM, which returns structured JSON — no OCR text layer in between. This is the
industry shift the project is built around: pure-OCR pipelines throw away layout, table
structure, and handwriting the moment they flatten a page into a string of characters; a vision
model reasons over the page image itself. By 2026, multimodal vision-language models routinely
outperform traditional OCR-then-NER pipelines on real-world documents precisely because they
never lose that layout information in the first place — the field has largely converged on this
approach for anything beyond clean, born-digital text extraction.

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
  CFA franc (`FCFA`/`CFA` → `XOF` or `XAF` depending on context) — a currency pair
  general-purpose LLM normalization gets wrong by default and the initial design didn't cover.
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

## Where this sits in the field, 2026 (literature-grounded, not asserted)

Document AI has moved through three broad phases: classical OCR + rule-based parsing, then
OCR + a fine-tuned layout/NER model (the LayoutLM family and its successors), and now
vision-language models reasoning directly over page images. By 2026 that third phase is the
default starting point for new document-extraction work rather than a novelty — industry
write-ups on document processing describe vision-first pipelines as outperforming classical
OCR+IDP on complex, real-world documents, precisely because a vision model reasons over layout,
tables, and handwriting jointly instead of first collapsing the page into a flat text stream that
downstream parsing has to reconstruct structure from.[^1] That's the industry direction this
project's architecture follows — not a contrarian bet, and not a novel one either.

That said, "vision-LLM" is not one thing, and the literature is specific about where the gap is:

- **Fine-tuned, task-specific layout models still lead on the classic benchmarks.** On FUNSD,
  CORD, and SROIE, models trained specifically for document layout — LayoutLMv3 (90.3 F1 on
  FUNSD, 96.6 F1 on CORD) and DocMamba (91.7 / 97.0 / 96.8 F1 on FUNSD / CORD / SROIE) — post
  higher scores than a general-purpose vision-LLM used zero-shot.[^2] DocIntel's own zero-shot
  numbers on the same benchmarks (92.5% field accuracy on CORD, 95.0% on SROIE — see below) sit
  *close to, not above,* those specialist results. Zero-shot vision-LLM extraction is competitive
  with, not superior to, purpose-trained layout models on their own home turf.
- **"Vision-LLM" spans a wide accuracy range depending on model tier.** One industry benchmark
  covering smaller/open-weight VLMs (DocOwl2, SmolDocling, Llama 3.2 Vision, DONUT) on complex
  real-world documents reported 42–67% accuracy[^1] — well below what this project measures for
  Route A (a frontier commercial model). Separately, published benchmarks of Claude specifically
  on invoice/receipt extraction report field-level accuracy in the 90–97.6% range depending on
  model version and document complexity.[^3] DocIntel's own Route A numbers (92.5–100% across
  its test sets) sit credibly inside that independently-reported range for the same model
  family — which is the calibration check that matters here: not "is this a good number in the
  abstract" but "is this consistent with what independent parties measure for the same model."
  Route B (open-weight, self-hosted) shows the wider swing the smaller-model literature would
  predict — 100% on clean/low-noise samples, 25–77% on noisier phone-photo receipts.
- **A deterministic post-processing layer over LLM output is documented best practice, not a
  novel technique.** Production guidance on LLM-based extraction pipelines converges on the same
  pattern this project uses: have the model emit a normalized-ish representation (ISO 8601 dates,
  etc.), then validate/convert with a deterministic library rather than trusting the model's
  string formatting — because most real production failures in these pipelines are exactly this
  class of normalization/unit error, not subtle semantic mistakes.[^4] `services/normalize.py`
  is a real, broad implementation of that pattern (45+ currencies, 6 OCR languages, US/EU/spaced/
  Swiss amount formats) — not a research contribution on top of it.
- **Map-reduce chunking for documents that exceed a model's practical context is likewise an
  established pattern**, not something this project originated: split into bounded chunks, extract
  per-chunk, merge — the same shape used broadly for long-document LLM workflows.[^5]
  `services/doc_merge.py`'s merge rules (concatenate list fields, take the last non-empty value
  for running totals, first non-null otherwise) are this project's specific, tested instance of
  that pattern for structured extraction rather than summarization.

## Is there novelty here? (asked and answered honestly)

No, not at the level of a new technique or model. Every architectural piece above — vision-LLM
extraction over OCR, deterministic post-processing as a safety layer, map-reduce chunking for
long documents — is documented, converged-on practice elsewhere in the field as of 2026, cited
above. What this project actually offers is a **real, honestly-measured, reasonably broad
implementation** of that converged-on architecture: three working extraction routes (not a
paper proposal), a normalization layer covering more currency/locale formats than most
example implementations, and results measured against real third-party documents and standard
benchmarks (CORD, SROIE, `invoice2data`) rather than a synthetic or cherry-picked set — with the
gaps stated plainly in "What is NOT built" above rather than glossed over. That is engineering
and measurement value, not research novelty, and this document isn't going to pretend otherwise.

## How DocIntel's numbers compare (summary table)

| Benchmark | DocIntel (this project) | Independently reported (2026) |
|---|---|---|
| CORD (receipts) | 92.5% field accuracy — Route A, zero-shot | LayoutLMv3 96.6 F1 · DocMamba 97.0 F1 (fine-tuned)[^2] |
| SROIE (receipts) | 95.0% overall — Route A, zero-shot | DocMamba 96.8 F1 (fine-tuned)[^2] |
| Invoices, general | 100% (small-N, multilingual) — Route A | Claude Sonnet reported 90–97.6% field accuracy depending on version/complexity[^3] |
| Small/open-weight VLMs, complex real-world docs | Route B: 25–100% depending on document quality | 42–67% accuracy reported industry-wide[^1] |

Read this table as a sanity check, not a leaderboard entry — DocIntel wasn't run on the exact same
splits as these external numbers, so it's directional consistency being verified, not a
head-to-head ranking.

## Future work

None of this is presented as finished. The honest next steps, in order of what would most
improve confidence in the numbers above rather than what's most publishable:

1. **A larger, more diverse benchmark.** The current corpus (CORD, SROIE, `invoice2data`, FUNSD,
   plus a hand-built FCFA sample) is real but modest in size and skews toward a handful of
   languages and currency families. A meaningfully larger, more linguistically diverse set with
   expert-annotated ground truth (rather than relying entirely on existing dataset labels) would
   tighten the accuracy estimates and surface currency/locale formats the normalization layer
   doesn't yet cover.
2. **A confidence-calibration study.** Every extraction returns a `_confidence` score, but nothing
   in this repo currently checks whether that score is *calibrated* — whether "0.9 confidence"
   actually means "right about 90% of the time" against human-annotated ground truth. That's a
   well-defined, checkable question this project hasn't answered yet.
3. **An ablation of the normalization layer itself.** Run the same benchmark with
   `services/normalize.py` disabled and measure the accuracy drop directly, to quantify (rather
   than assert) how much of the measured accuracy the deterministic layer is actually responsible
   for versus the model's raw output.
4. **Automatic route escalation based on confidence**, rather than the current fixed per-request
   route choice — e.g., escalate from Route C to Route A when confidence falls below a threshold.
   Given the accuracy gap already measured between routes on noisier documents (Route C 28.5% vs.
   Route A 92.5% on the same CORD receipts), this is a concrete, testable way to trade a modest
   cost increase for a large accuracy gain only on the documents that actually need it.
5. **Explicit currency/locale coverage accounting.** `services/normalize.py` covers a broad but
   finite set of formats; stating precisely which format families are and aren't covered (rather
   than "45+ currencies" as a headline number) would make the layer's real limits legible instead
   of implied.

None of the above is currently implemented — this section is a stated intention, not a claim.

## Real, reproducible results

Full methodology, corpus composition, and scoring rules: [eval/BENCHMARK.md](eval/BENCHMARK.md).
Reproducible via `python eval/build_corpus.py` + `python eval/run_benchmark.py`, and the same
numbers are served live (so this document and the running app can't silently diverge) via
`GET /benchmarks`. See BENCHMARK.md for the current corpus size and per-route numbers — this
document doesn't duplicate them so there's exactly one place they can go stale.

## Sources

[^1]: Industry benchmarking of vision-AI document processing vs. classical OCR/IDP, including a
    42–67% accuracy range for general-purpose VLMs (DocOwl2, SmolDocling, Llama 3.2 Vision, DONUT)
    on complex real-world documents. [Parseur, "Vision AI Document Processing — The Complete 2026
    Guide"](https://parseur.com/blog/vision-ai-document-processing).
[^2]: Fine-tuned layout-model F1 scores on FUNSD/CORD/SROIE (LayoutLMv3, DocMamba, HIP). See the
    [DocMamba paper](https://arxiv.org/pdf/2409.11887) and the [HIP paper](https://arxiv.org/pdf/2411.01139)
    for the primary numbers; cross-referenced via the [CodeSOTA OCR
    leaderboard](https://www.codesota.com/ocr).
[^3]: Independently reported Claude Sonnet field-level accuracy on invoice/receipt extraction
    (90% for Sonnet 3.5 in one study, 97.6% for Sonnet 4.6 "on complex layouts" in another, 94.3%
    on receipts in a third). [AImultiple, "Invoice OCR Benchmark"](https://aimultiple.com/invoice-ocr);
    [TokenMix, "Best AI for Document Processing 2026"](https://tokenmix.ai/blog/best-ai-for-document-processing).
    These are vendor/industry benchmarks, not peer-reviewed papers — treated here as directional
    context, not ground truth.
[^4]: Production best-practice guidance on LLM output normalization as a deterministic
    post-processing/validation step, and normalization/unit errors as a dominant real-world
    failure mode. [Medium, "Best Practices for Handling Dates in Structured Output in
    LLM"](https://medium.com/@jamestang/best-practices-for-handling-dates-in-structured-output-in-llm-2efc159e1854).
[^5]: Map-reduce as an established pattern for long-document LLM processing (split into bounded
    chunks, extract/summarize per chunk, merge). [F22 Labs, "Map Reduce for Large Document
    Summarization with LLMs"](https://www.f22labs.com/blogs/map-reduce-for-large-document-summarization-with-llms/).

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
