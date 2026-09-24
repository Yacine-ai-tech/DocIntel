# DocIntel: Vision-LLM-First Document Extraction

## What This Is

DocIntel extracts structured data from documents — invoices, receipts, contracts, forms,
financial reports — using a vision-LLM-first approach: page images are passed directly to a
vision-capable LLM, which returns structured JSON, with no intermediate OCR text layer.
Pure-OCR pipelines discard layout, table structure, and handwriting information the moment a
page is flattened into a string of characters; a vision model reasons over the page image
itself. By 2026, multimodal vision-language models routinely outperform traditional
OCR-then-NER pipelines on real-world documents for exactly this reason, and the field has
largely converged on vision-first extraction for anything beyond clean, born-digital text.

Three extraction routes are available, selected per request or by default:

- **Route A** — Claude Sonnet 4.6 Vision (hosted, metered; per-call cost tracked via
  `litellm.completion_cost()`).
- **Route B** — a self-hosted Ollama vision model (Qwen 2.5-VL 7B validated; see
  `eval/BENCHMARK.md` for why Llama 3.2 Vision was evaluated and not adopted), run on the same
  host, on a local network, or on separate hardware under the operator's control. No
  third-party inference API in this path, and no per-call cost.
- **Route C** — Surya OCR (layout-aware, GPU) as the primary engine, with Tesseract as an
  automatic fallback when a GPU is unavailable or Surya returns no text, followed by LLM-based
  cleanup. Used when vision-LLM cost is prohibitive, image quality is too low for a vision
  model, or as an automatic fallback if Routes A/B fail.

Multi-page documents (up to `MAX_PDF_PAGES`, default 200) are handled by chunking pages across
multiple vision calls and merging results (`services/doc_merge.py`): list fields concatenate
across chunks, running-total fields take the last non-empty chunk, and other fields take the
first non-null value observed.

## Deterministic Post-Processing

LLMs are unreliable at locale-specific formatting, so extracted amounts, currencies, and dates
pass through a deterministic normalization layer (`services/normalize.py`) after extraction —
the model still performs the extraction; this layer standardizes how the result is represented.

- **Amounts**: US (`1,234.56`), EU (`1.234,56`), space-grouped (`1 234 567`), Swiss
  (`1'234.56`), and parenthesized-negative formats convert to a plain float. A value that does
  not match a known pattern is left unchanged rather than guessed at.
- **Currency → ISO 4217**: symbols and codes for 40+ currencies, including the West and
  Central African CFA franc (`FCFA`/`CFA` → `XOF` or `XAF` depending on context) — a
  currency pair general-purpose LLM normalization typically gets wrong by default.
- **Dates → ISO 8601** via `dateparser`, with a common-format fallback when unavailable.

Covered by `tests/test_normalize.py` (US, EU, Japanese, Indian, UK, Swiss, and FCFA amount
formats; ISO currencies; date parsing).

## What Is Not Built

- **No layout/structure model.** DocIntel does not construct a bounding-box graph, reading-order
  edges, or a layout tree. The only per-element bounding-box output anywhere in the codebase is
  Surya OCR's flat per-line list (an optional fallback path) and pdfplumber's per-table
  bounding boxes from `/extract-tables`; neither is a graph, and neither feeds into extraction
  quality — they are incidental output of two specific routes.
- **No table-structure F1, layout-hierarchy, or character-error-rate benchmark.** What is
  measured (below) is field-level extraction accuracy — did the model correctly identify the
  vendor, total, date, and line items. That is a distinct, directly useful metric, but it is
  not layout precision or CER.
- **No DocTR as a second layout-aware OCR fallback alongside Surya.** DocTR was evaluated and
  is not included: Surya OCR already measures 96.3% field accuracy on the FCFA sub-corpus and
  97.4% on the global sample (see `BENCHMARK.md`), and DocTR is a comparable-tier layout-aware
  engine rather than a documented improvement over Surya for this task. A third OCR fallback
  behind Tesseract and Surya would add installation and maintenance surface without an
  accuracy gain to justify it.

## Where This Sits in the Field, 2026

Document AI has moved through three broad phases: classical OCR with rule-based parsing, then
OCR paired with a fine-tuned layout/NER model (the LayoutLM family and its successors), and now
vision-language models reasoning directly over page images. By 2026, the third phase is the
default starting point for new document-extraction work. Industry analysis of document
processing describes vision-first pipelines as outperforming classical OCR-plus-IDP on complex,
real-world documents, because a vision model reasons over layout, tables, and handwriting
jointly rather than first collapsing the page into a flat text stream that downstream parsing
must reconstruct structure from.[^1] This is the direction DocIntel's architecture follows — an
established industry pattern, not a novel one.

The literature is specific about where the remaining gaps are:

- **Fine-tuned, task-specific layout models still lead on standard benchmarks.** On FUNSD, CORD,
  and SROIE, models trained specifically for document layout — LayoutLMv3 (90.3 F1 on FUNSD,
  96.6 F1 on CORD) and DocMamba (91.7 / 97.0 / 96.8 F1 on FUNSD / CORD / SROIE) — score higher
  than a general-purpose vision-LLM used zero-shot.[^2] DocIntel's zero-shot results on the same
  benchmarks (92.5% field accuracy on CORD, 95.0% on SROIE) sit close to, not above, those
  specialist results — zero-shot vision-LLM extraction is competitive with, rather than superior
  to, purpose-trained layout models on their own benchmarks.
- **Vision-LLM accuracy varies widely by model tier.** An industry benchmark of smaller,
  open-weight vision-language models (DocOwl2, SmolDocling, Llama 3.2 Vision, DONUT) on complex
  real-world documents reported 42–67% accuracy[^1] — well below DocIntel's measured Route A
  results (a frontier commercial model). Separately, published benchmarks of Claude specifically
  on invoice and receipt extraction report field-level accuracy in the 90–97.6% range depending
  on model version and document complexity.[^3] DocIntel's Route A results (92.5–100% across its
  test sets) fall within that independently reported range for the same model family, which is
  the relevant calibration check: consistency with what independent parties measure for the same
  model, rather than a standalone claim. Route B (open-weight, self-hosted) initially showed a
  wider accuracy range consistent with the smaller-model literature (25–77% depending on document
  quality); a GPU-accelerated configuration with a corrected response-length limit and
  deskew preprocessing raised this to 97.8% overall (89.9% on the global sample, 100% on the
  French/FCFA sample) — see `BENCHMARK.md`.
- **A deterministic post-processing layer over LLM output is documented best practice, not a
  novel technique.** Production guidance on LLM-based extraction pipelines converges on the same
  pattern used here — have the model emit a near-normalized representation, then validate and
  convert with a deterministic library rather than trusting the model's own string formatting —
  because normalization and unit errors are a dominant real-world failure mode in these
  pipelines, more so than semantic extraction errors.[^4] `services/normalize.py` is a broad
  implementation of that pattern (45+ currencies, 6 OCR languages, multiple amount formats),
  not a research contribution on top of it.
- **Map-reduce chunking for documents exceeding a model's practical context window is likewise
  an established pattern**, used broadly across long-document LLM workflows.[^5]
  `services/doc_merge.py`'s merge rules (concatenate list fields, take the last non-empty value
  for running totals, first non-null value otherwise) are a specific, tested instance of that
  pattern applied to structured extraction rather than summarization.

## Is There Novelty Here?

Not at the level of a new technique or model. Every architectural element described above —
vision-LLM extraction in place of OCR, deterministic post-processing as a safety layer,
map-reduce chunking for long documents — is documented, converged-on practice in the field as
of 2026, cited above. What this project offers is a real, broadly scoped, honestly measured
implementation of that converged-on architecture: three working extraction routes, a
normalization layer covering a wide range of currency and locale formats, and results measured
against real third-party documents and standard benchmarks (CORD, SROIE, `invoice2data`) rather
than a synthetic or curated set, with limitations stated directly rather than omitted. That is
engineering and measurement value, not research novelty.

## How DocIntel's Numbers Compare

| Benchmark | DocIntel | Independently reported (2026) |
|---|---|---|
| CORD (receipts) | 92.5% field accuracy — Route A, zero-shot | LayoutLMv3 96.6 F1 · DocMamba 97.0 F1 (fine-tuned)[^2] |
| SROIE (receipts) | 95.0% overall — Route A, zero-shot | DocMamba 96.8 F1 (fine-tuned)[^2] |
| Invoices, general | 100% (small sample, multilingual) — Route A | Claude Sonnet reported 90–97.6% field accuracy, depending on version and complexity[^3] |
| Smaller open-weight VLMs, complex real-world documents | Route B: 97.8% (GPU-accelerated) | 42–67% accuracy reported industry-wide[^1] |

This table is a directional consistency check rather than a head-to-head ranking — DocIntel was
not evaluated on the identical splits used in these external studies. Route B's 97.8% exceeds
the 42–67% range cited for small, open-weight VLMs on complex real-world documents; this
reflects a document mix (structured invoices and receipts) that is materially less demanding
than the "complex real-world" documents those studies target, rather than a claim that this
model class outperforms that literature on harder inputs generally.

## Future Work

The next steps most likely to improve confidence in the results above:

1. **A larger, more diverse benchmark.** The current corpus (CORD, SROIE, `invoice2data`, FUNSD,
   plus the FCFA sample) is real but modest in size and skews toward a small number of languages
   and currency families. A larger, more linguistically diverse set with expert-annotated
   ground truth would tighten the accuracy estimates and surface currency and locale formats the
   normalization layer does not yet cover.
2. **A confidence-calibration study.** Every extraction returns a confidence score, but nothing
   in this project currently verifies that the score is calibrated — that a 0.9 confidence value
   corresponds to roughly 90% correctness against human-annotated ground truth.
3. **An ablation of the normalization layer.** Running the same benchmark with normalization
   disabled would quantify, rather than assert, how much of the measured accuracy the
   deterministic layer contributes versus the model's raw output.
4. **Confidence-based automatic route escalation** — for example, escalating from Route C to
   Route A when confidence falls below a threshold, trading a modest cost increase for accuracy
   on documents that need it, rather than a fixed per-request route choice.
5. **Explicit currency and locale coverage accounting** — stating precisely which format
   families are and are not covered by the normalization layer, rather than a single aggregate
   count.

## Reproducibility

Full methodology, corpus composition, and scoring rules: [eval/BENCHMARK.md](eval/BENCHMARK.md).
Reproducible via `python eval/build_corpus.py` followed by `python eval/run_benchmark.py`; the
same figures are served live via `GET /benchmarks`, so the documentation and the running
application cannot silently diverge.

## Sources

[^1]: Industry benchmarking of vision-AI document processing against classical OCR/IDP,
    including a 42–67% accuracy range for general-purpose VLMs (DocOwl2, SmolDocling, Llama 3.2
    Vision, DONUT) on complex real-world documents. [Parseur, "Vision AI Document Processing —
    The Complete 2026 Guide"](https://parseur.com/blog/vision-ai-document-processing).
[^2]: Fine-tuned layout-model F1 scores on FUNSD/CORD/SROIE (LayoutLMv3, DocMamba, HIP). See the
    [DocMamba paper](https://arxiv.org/pdf/2409.11887) and the [HIP
    paper](https://arxiv.org/pdf/2411.01139) for primary figures, cross-referenced via the
    [CodeSOTA OCR leaderboard](https://www.codesota.com/ocr).
[^3]: Independently reported Claude Sonnet field-level accuracy on invoice/receipt extraction
    (90% for Sonnet 3.5 in one study, 97.6% for Sonnet 4.6 on complex layouts in another, 94.3%
    on receipts in a third). [AImultiple, "Invoice OCR Benchmark"](https://aimultiple.com/invoice-ocr);
    [TokenMix, "Best AI for Document Processing 2026"](https://tokenmix.ai/blog/best-ai-for-document-processing).
    These are vendor/industry benchmarks rather than peer-reviewed papers, treated here as
    directional context.
[^4]: Production best-practice guidance on LLM output normalization as a deterministic
    post-processing step, and normalization/unit errors as a dominant real-world failure mode.
    [Medium, "Best Practices for Handling Dates in Structured Output in
    LLM"](https://medium.com/@jamestang/best-practices-for-handling-dates-in-structured-output-in-llm-2efc159e1854).
[^5]: Map-reduce as an established pattern for long-document LLM processing. [F22 Labs, "Map
    Reduce for Large Document Summarization with
    LLMs"](https://www.f22labs.com/blogs/map-reduce-for-large-document-summarization-with-llms/).

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
