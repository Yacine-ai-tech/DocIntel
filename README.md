# DocIntel
[![CI](https://github.com/Yacine-ai-tech/DocIntel/actions/workflows/ci.yml/badge.svg)](https://github.com/Yacine-ai-tech/DocIntel/actions/workflows/ci.yml) [![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)

**Vision-first document AI. Drop a PDF, image, or Office file, get structured JSON in under 2 seconds. Local or cloud.**
> **Live dashboard:** https://docintel.ysiddo-ai-projects.app/  ·  drag-drop a PDF/image/PPTX/DOCX/XLSX.
> On-demand backend (first request ~30–60 s to wake).
> Self-hosting: see [SELF_HOSTING.md](SELF_HOSTING.md). Route B local vision spins up a GPU on demand (~4–5 min cold).

## What It Does

- **3 extraction routes**: Claude Sonnet 4.6 Vision (Route A), **Ollama vision** (Route B - private/`$0`-per-page — Qwen 2.5-VL 7B is the validated model, and the route is model-agnostic via `OLLAMA_MODEL` for any other Ollama-served vision model, never a third-party inference API; `ROUTE_B_MODE=local` runs Ollama on the same host as the app, `ROUTE_B_MODE=remote` points at Ollama on hardware you control elsewhere — LAN or over the internet), Tesseract+LLM (Route C fallback)
- **Multi-currency & multi-locale**: amounts in US/EU/spaced/Swiss formats and 45+ currencies (USD, EUR, GBP, JPY, INR, CNY, XOF/FCFA, …) are normalized to ISO 4217 + float; dates to ISO 8601 — a deterministic layer (`services/normalize.py`) on top of the LLM. OCR runs `eng+fra+deu+nld+spa+ita`.
- **Inputs**: PDF (native or scanned), PNG, JPEG, PPTX, DOCX, XLSX — auto-detected. PDFs are rendered per page; images flow straight through to OCR/vision; PPTX/DOCX/XLSX are read natively (`services/ocr_extractor.py`: `extract_text_native_office`) since they're ZIP archives of real XML text, not renderable images — routing one through the image OCR path fails outright (PIL can't open a zip as a raster image) rather than just extracting badly, which is why this has its own dedicated path instead of falling through the vision routes.
- **Multi-page & large documents**: every page is processed and fields aggregated across pages (a total on a later page, multi-page contracts). **100+ page PDFs** are handled via map-reduce — pages are split into chunks, extracted concurrently, and merged (`MAX_PDF_PAGES` default 200). The OCR route concatenates/chunks full-document text the same way.
- **Handwriting & mixed languages**: the vision routes read handwritten entries and EN/FR/DE/NL/ES/IT documents; numbers are normalized (EU `1.234,56` → `1234.56`; West-African `1 003 000 FCFA` → `1003000`) and currencies to ISO-4217, including the West-African CFA franc (**FCFA/CFA → XOF**, Central-African → XAF).
- **Doc-type-aware schemas**: invoice, contract, receipt, financial_report, auction_listing, form
- **Confidence scores** on every extraction; retry-on-bad-JSON for reliability
- **`/classify-image` endpoint**: vision-first object classification for auction/inventory aggregation
- **Batch at scale**: bounded-concurrency async jobs that process hundreds/thousands of files with per-file error isolation
- **`/process`**: one-shot upload → auto-classify → multi-page extract → JSON
- **`/extract-fields`**: generic form label→value extraction, independent of the invoice/contract/receipt schemas
- **n8n / workflow-automation integration**: `/batch/upload` accepts a `webhook_url` — DocIntel POSTs results to it on completion, no polling needed. See [docs/n8n](docs/n8n/README.md)
- **Mobile scan**: the dashboard's Mobile Scanner page generates a QR pairing code; scanning it opens a phone-camera capture page that uploads straight into Route B extraction — no app install. Requires HTTPS (see [SELF_HOSTING.md](SELF_HOSTING.md))
- **Full web dashboard** at `/`

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in API keys
uvicorn api:app --port 8001
```

Open http://localhost:8001/

## Endpoints

| Method | Path                       | Purpose                                       |
|--------|----------------------------|-----------------------------------------------|
| GET    | /health                    | Liveness check                                |
| GET    | /benchmarks                | Live-served benchmark numbers (from `eval/BENCHMARK.md`), so the dashboard and this doc can't silently diverge |
| POST   | /process                   | One-shot: upload → auto-classify → multi-page extract (blocking) |
| POST   | /process/async             | Same as /process but returns a `job_id` immediately and runs in the background — for slow routes behind a proxy with its own timeout; poll via /batch/{job_id} |
| POST   | /classify                  | Fast doc-type classification                  |
| POST   | /classify-image            | Vision-first object classification            |
| POST   | /extract                   | Full extraction (file + route + doc_type), multi-page |
| POST   | /extract/marker            | PDF → Markdown via Marker (born-digital PDF text structure) |
| POST   | /extract/text               | Full document text (RAG-ingestion shape), synchronous — see /extract/text/batch for large documents |
| POST   | /extract/text/batch        | Async /extract/text — for documents too large/slow to finish inside a synchronous request; poll via /batch/{job_id} |
| POST   | /extract-llm               | LLM extract from raw text                     |
| POST   | /extract-tables             | PDF tables via pdfplumber                     |
| POST   | /extract-fields            | Generic form field extraction (label → value) |
| POST   | /batch/upload               | Start background batch job (structured extraction, optional `webhook_url` — POSTed to on completion, see [docs/n8n](docs/n8n/README.md)) |
| GET    | /batch/{job_id}            | Job status                                    |
| GET    | /batch/{job_id}/results    | Job results                                   |
| POST   | /camera/pair               | Desktop: generate a mobile pairing token + QR |
| GET    | /camera/qr/{token}         | Raw QR code image bytes for a pairing token   |
| POST   | /camera/upload             | Phone: upload a photo for Route B extraction  |
| GET    | /camera/status/{token}     | Desktop: poll for the phone's upload result   |

## Architecture

```
              ┌─────────────┐        PDFs → render EVERY page (pdf_to_pngs)
PDF / IMG ───►│   api.py    │───►    or extract full-document text (extract_text_from_pdf)
              │  FastAPI    │              │
              └──────┬──────┘              ▼
                     │            ┌──────────────────┐
        route ┌──────┼──────┐     │ multi-page images │
              ▼      ▼      ▼     └──────────────────┘
        vision_   vision_   ocr_extractor ─► llm_extractor
        (route_a) (route_b)   (Tesseract)      (text → JSON)
         Claude    Ollama      multilingual   Haiku cleanup
         Vision    Vision      OCR            + confidence
      (Route A)  (Route B)                   (Route C)
    Llama 3.2 / Qwen             └──────┴──────────────┴───────────────┘
                                  ▼
            structured JSON  { ..fields.., _confidence, _pages }
```

PPTX/DOCX/XLSX skip that whole diagram: they're detected before the PDF/image branch
(ZIP signature + internal `ppt/`/`word/`/`xl/` part check, since all three OOXML
formats share the same ZIP signature) and read directly via `python-pptx` /
`python-docx` / `openpyxl` — real text runs off the XML, not pixels through OCR.
There's no page image to render and no vision model in the loop; sending one of
these through the image path instead fails outright rather than just badly,
since PIL can't open a ZIP archive as a raster image.

## Validation

Validated on **real, multilingual third-party invoices** (EN/FR/DE/NL, `invoice2data` test
set) — see [eval/EVAL_REAL.md](eval/EVAL_REAL.md). Route A (Claude Vision) and Route C
(Tesseract + LLM) both score **100%** on the fields each document carries; `/classify-image`
returns invoice 0.98–0.99. Reproduce with `bash eval/fetch_real_invoices.sh` then
`python eval/run_real_eval.py --route vision_route_a`.

## Scope & Notes

- **Multi-page / large docs**: up to `MAX_PDF_PAGES` (default **200**) per document; documents larger than `VISION_PAGES_PER_CALL` (default 8) pages are chunked and merged via map-reduce. Vision pages are downscaled past `VISION_MAX_EDGE` px to bound token cost.
- **Handwriting**: handled by the vision routes (Route A is strongest). The pure-OCR route (Route C) is weaker on handwriting — use a vision route for handwritten docs.
- **Currencies**: ISO-4217 generic; EU decimal/comma and West-African FCFA (space-grouped, no decimal subunit → XOF/XAF) formats normalized. Ambiguous thousands/decimal separators on low-quality scans can still mislead the pure-OCR route.
- **Route C non-English**: install the matching Tesseract packs (`tesseract-ocr-fra/deu/nld/...`); falls back to English automatically if a pack is missing.

## Benchmark

A multi-type, multilingual benchmark (receipts, invoices, forms; including multi-page and
handwriting) is reproducible via `python eval/build_corpus.py` and scored with
`python eval/run_benchmark.py` — current corpus size and full results in
[eval/BENCHMARK.md](eval/BENCHMARK.md), not duplicated here to avoid the two drifting apart.

| Route | Model | Test set | Accuracy |
|-------|-------|----------|----------|
| A — vision_route_a | Claude Sonnet 4.6 Vision | multilingual invoices (multi-page) | **100%** |
| A — vision_route_a | Claude Sonnet 4.6 Vision | phone-photo receipts (CORD) | **92.5%** |
| A — vision_route_a | Claude Sonnet 4.6 Vision | SROIE world-standard receipts | **95%** |
| B — vision_route_b | Ollama Qwen 2.5-VL 7B (self-hosted GPU) | CORD phone-photo receipts | **77%** |
| B — vision_route_b | Ollama Qwen 2.5-VL 7B (self-hosted GPU) | French + FCFA (XOF) sample | **100%** |
| C — ocr_fallback | Tesseract + Claude Haiku | clean invoices | **100%** |
| C — ocr_fallback | Tesseract + Claude Haiku | CORD phone-photo receipts | **28.5%** |

Full corpus size, per-route sample sizes, and reproduction commands: [eval/BENCHMARK.md](eval/BENCHMARK.md)
— not duplicated here beyond headline numbers, so there's exactly one place they can go stale.
Note: an earlier version of this table also listed Llama 3.2 Vision 11B on Route B — removed,
since `eval/BENCHMARK.md`'s own testing found it fails to load on current Ollama builds (or
scores 0/7 on the one build where it does load); Qwen 2.5-VL is the only currently-validated
local model.

## Tests

91 test functions across smoke, API, security, AI-pipeline, database, extraction, batch, and benchmark scripts:

```bash
pytest tests/ -q
```

## Research Notes

DocIntel's architecture (vision-LLM-first extraction, avoiding OCR character-fragmentation
entirely on Routes A/B) is described in [RESEARCH.md](RESEARCH.md), including a literature-backed
comparison of DocIntel's measured numbers against independently-published 2026 benchmarks
(LayoutLMv3, DocMamba, Claude Sonnet invoice-extraction studies) and a plain answer to "is any of
this novel" — no, not at the technique level; the value here is a real, broad, honestly-measured
implementation of practices the field has already converged on. No quantitative research-grade
benchmark (table-structure F1, layout precision, CER) has been run yet — earlier numbers
published here were generated by a random-number simulator, not measured, and have been removed.
The one benchmark that *is* real, with real documents and ground truth, is the eval above (see
[eval/BENCHMARK.md](eval/BENCHMARK.md)).

## License & Enterprise Use (Dual-License)

This project is open-source under the **AGPL-3.0 License**. Free for researchers, students, and open-source projects.
Commercial license: see [COMMERCIAL.md](COMMERCIAL.md).



![telemetry](https://gateway.ysiddo-ai-projects.app/pixel.png)
