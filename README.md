# DocIntel

[![CI](https://github.com/Yacine-ai-tech/DocIntel/actions/workflows/ci.yml/badge.svg)](https://github.com/Yacine-ai-tech/DocIntel/actions/workflows/ci.yml) [![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)

**Vision-first document intelligence.** DocIntel extracts structured, schema-typed data from
invoices, receipts, contracts, forms, and financial reports — PDFs, images, and native Office
files — via three interchangeable extraction routes, with deterministic normalization of
currencies, amounts, and dates layered on top.

**Live demo:** https://docintel.ysiddo-ai-projects.app/ — drag-and-drop a PDF, image, PPTX,
DOCX, or XLSX. The backend runs on demand; the first request after idle may take up to a
minute to respond. Self-hosting instructions: [SELF_HOSTING.md](SELF_HOSTING.md).

## What It Does

- **Three extraction routes**, selectable per request or by default:
  - **Route A** — Claude Sonnet 4.6 Vision (hosted, metered).
  - **Route B** — a self-hosted Ollama vision model (Qwen 2.5-VL 7B, validated; the route is
    model-agnostic via `OLLAMA_MODEL`), run on the same host or on separate hardware you
    control. No third-party inference API in this path; no per-call cost.
  - **Route C** — Surya OCR (GPU, layout-aware) as the primary engine, with Tesseract as an
    automatic fallback on systems without a GPU, followed by LLM-based cleanup.
- **Multi-currency and multi-locale normalization.** Amounts in US, EU, space-grouped, and
  Swiss formats, and 45+ currencies (including the West African CFA franc, normalized to ISO
  4217 code `XOF`/`XAF`), are converted to a canonical float via a deterministic
  post-processing layer (`services/normalize.py`), separate from the extraction model itself.
  Dates are normalized to ISO 8601. OCR covers English, French, German, Dutch, Spanish, and
  Italian.
- **File types**: PDF (native or scanned), PNG, JPEG, PPTX, DOCX, and XLSX, auto-detected on
  upload. Office formats are parsed natively from their underlying XML rather than rendered
  and passed through an image pipeline.
- **Multi-page and large documents.** Every page is processed and fields are aggregated across
  the full document (a total appearing on a later page, a multi-page contract). Documents
  beyond a page-count threshold are split into chunks, extracted concurrently, and merged.
  Up to 200 pages per document by default (`MAX_PDF_PAGES`).
- **Handwriting and mixed-language documents** are read by the vision routes (Route A is the
  strongest on handwriting); numbers and currencies are normalized regardless of source locale,
  including French-language West African formats (space-grouped thousands, no decimal
  subunit).
- **Schema-typed extraction** for invoices, contracts, receipts, financial reports, auction
  listings, and generic forms, with a confidence score on every extraction and automatic
  retry on malformed model output.
- **`/classify-image`** — vision-first object classification, for use cases such as
  auction-listing or inventory-photo aggregation.
- **Batch processing** with bounded concurrency and per-file error isolation, for jobs
  spanning hundreds to thousands of documents.
- **Workflow-automation integration**: `/batch/upload` accepts a `webhook_url` and posts
  results to it on completion — see [docs/n8n](docs/n8n/README.md).
- **Mobile capture**: the dashboard's Mobile Scanner page generates a QR code that opens a
  phone-camera capture flow feeding directly into Route B extraction, with no app install.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in API keys
uvicorn api:app --port 8001
```

Then open http://localhost:8001/.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Liveness check |
| GET | /benchmarks | Benchmark figures served live from `eval/BENCHMARK.md` |
| POST | /process | One-shot upload → classify → multi-page extract |
| POST | /process/async | Asynchronous variant of `/process`; poll via `/batch/{job_id}` |
| POST | /classify | Document-type classification |
| POST | /classify-image | Vision-first object classification |
| POST | /extract | Full extraction (file, route, document type), multi-page |
| POST | /extract/marker | PDF → Markdown, for born-digital PDF text structure |
| POST | /extract/text | Full document text, in the shape used for RAG ingestion |
| POST | /extract/text/batch | Asynchronous variant of `/extract/text` |
| POST | /extract-llm | Structured extraction from raw text |
| POST | /extract-tables | Table extraction from PDFs |
| POST | /extract-fields | Generic label → value form-field extraction |
| POST | /batch/upload | Start a background batch job, with optional `webhook_url` |
| GET | /batch/{job_id} | Job status |
| GET | /batch/{job_id}/results | Job results |
| POST | /camera/pair | Generate a mobile pairing token and QR code |
| GET | /camera/qr/{token} | QR code image for a pairing token |
| POST | /camera/upload | Upload a phone-captured photo for Route B extraction |
| GET | /camera/status/{token} | Poll for a phone upload's result |

## Architecture

```
                ┌─────────────┐
PDF / image ───►│   api.py    │─── render each page, or extract full-document text
                │  FastAPI    │
                └──────┬──────┘
             route ┌───┼────┐
                   ▼   ▼    ▼
              Route A  Route B  Route C
              Claude   Ollama   Surya OCR (primary, GPU) or
              Vision   Vision   Tesseract (fallback) + LLM cleanup
                   └───┴────┘
                        ▼
        structured JSON { fields..., _confidence, _pages }
```

PPTX, DOCX, and XLSX files bypass this pipeline entirely: they are detected by their ZIP
signature and internal structure, then parsed directly via `python-pptx`, `python-docx`, and
`openpyxl` — real text extracted from the underlying XML, with no rendering or vision model
involved.

## Validation

Validated against real, third-party, multilingual invoices (English, French, German, Dutch;
the `invoice2data` test set — see [eval/EVAL_REAL.md](eval/EVAL_REAL.md)). Route A and
Route C both score 100% on the fields present in each document; `/classify-image` returns
0.98–0.99 confidence on real invoice images. Full results, corpus composition, and
reproduction commands: [eval/BENCHMARK.md](eval/BENCHMARK.md).

## Scope and Limitations

- **Multi-page documents** are supported up to `MAX_PDF_PAGES` (default 200); documents beyond
  `VISION_PAGES_PER_CALL` (default 8) pages are chunked and merged. Vision pages are downscaled
  past `VISION_MAX_EDGE` pixels to bound token cost.
- **Handwriting** is handled by the vision routes, with Route A the strongest; Route C
  (OCR-based) is weaker on handwritten text.
- **Currency and locale coverage** spans ISO-4217-listed currencies plus West African FCFA
  formatting; ambiguous thousands/decimal separators on low-quality scans can still mislead
  the OCR-only route.
- **Route C's OCR engine** is GPU-dependent for its primary path (Surya); on systems without a
  GPU, it falls back automatically to Tesseract, at lower accuracy (see Benchmark). Non-English
  Tesseract fallback requires the matching language pack (`tesseract-ocr-fra`, `-deu`, `-nld`,
  etc.); English is used automatically if a required pack is absent.

## Benchmark

| Route | Model | Test set | Field accuracy |
|-------|-------|----------|-----------------|
| A | Claude Sonnet 4.6 Vision | Multilingual invoices, multi-page | 100% |
| A | Claude Sonnet 4.6 Vision | CORD receipts (phone photographs) | 92.5% |
| A | Claude Sonnet 4.6 Vision | SROIE (ICDAR-2019 Task 3) | 95.0% |
| B | Ollama Qwen 2.5-VL 7B (self-hosted GPU) | Global sample (invoices + CORD receipts) | 89.9% |
| B | Ollama Qwen 2.5-VL 7B (self-hosted GPU) | French / FCFA sample | 100% |
| C | Surya OCR (GPU) + LLM cleanup | French / FCFA sub-corpus | 96.3% |
| C | Surya OCR (GPU) + LLM cleanup | Global sample | 97.4% |

Full methodology, corpus sizes, and reproduction commands: [eval/BENCHMARK.md](eval/BENCHMARK.md).

## Tests

91 test functions across smoke, API, security, extraction, database, batch, and benchmark paths:

```bash
pytest tests/ -q
```

## Research

The architectural reasoning behind vision-LLM-first extraction, a literature-grounded
comparison of DocIntel's measured results against independently published 2026 benchmarks,
and an explicit account of what is and isn't novel here are in [RESEARCH.md](RESEARCH.md).

## Anonymous Telemetry

On startup, a background thread sends one HTTP POST, at most once per six hours per running
instance: `{"service": "DocIntel", "event": "startup", "instance_id": "<random identifier>"}`
— no document content, filenames, extraction results, API keys, or configuration is included.
The instance identifier is a randomly generated value, not derived from any hardware
identifier. Destination is the `TELEMETRY_URL` environment variable, which defaults to blank
(no request is made without one being set); `TELEMETRY_OPT_OUT=true` disables it explicitly.

## License

Open-source under the AGPL-3.0 License, free for researchers, students, and open-source
projects. A commercial license is available for closed-source or enterprise use — see
[COMMERCIAL.md](COMMERCIAL.md).

![telemetry](https://gateway.ysiddo-ai-projects.app/pixel.png)
