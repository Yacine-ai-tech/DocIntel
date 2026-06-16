# DocIntel

**Vision-first document AI. Drop a PDF or image, get structured JSON in under 2 seconds. Local or cloud.**

## What It Does

- **3 extraction routes**: Claude Sonnet 4.6 Vision (premium), Ollama Llama 3.2 Vision (local/private), Tesseract+LLM (fallback)
- **Multi-page documents**: every page of a PDF is rendered and sent to the vision model together, so fields are aggregated across pages (totals on a later page, multi-page contracts). The OCR route concatenates full-document text.
- **Handwriting & mixed languages**: the vision routes read handwritten entries and EN/FR/DE/NL/ES/IT documents; numbers are normalized (EU `1.234,56` → `1234.56`; West-African `1 003 000 FCFA` → `1003000`) and currencies to ISO-4217, including the West-African CFA franc (**FCFA/CFA → XOF**, Central-African → XAF).
- **Doc-type-aware schemas**: invoice, contract, receipt, financial_report, auction_listing, form
- **Confidence scores** on every extraction; retry-on-bad-JSON for reliability
- **`/classify-image` endpoint**: vision-first object classification for auction/inventory aggregation
- **Batch at scale**: bounded-concurrency async jobs that process hundreds/thousands of files with per-file error isolation
- **`/process`**: one-shot upload → auto-classify → multi-page extract → JSON
- **Drag-and-drop demo** at `/demo`

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in API keys
uvicorn api:app --port 8001
```

Open http://localhost:8001/demo

## Endpoints

| Method | Path                       | Purpose                                       |
|--------|----------------------------|-----------------------------------------------|
| GET    | /health                    | Liveness check                                |
| POST   | /process                   | One-shot: upload → auto-classify → multi-page extract |
| POST   | /classify                  | Fast doc-type classification                  |
| POST   | /classify-image            | Vision-first object classification            |
| POST   | /extract                   | Full extraction (file + route + doc_type), multi-page |
| POST   | /extract-llm               | LLM extract from raw text                     |
| POST   | /extract-tables            | PDF tables via pdfplumber                     |
| POST   | /batch/upload              | Start background batch job                    |
| GET    | /batch/{job_id}            | Job status                                    |
| GET    | /batch/{job_id}/results    | Job results                                   |

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
        (premium) (local)   (Tesseract)      (text → JSON)
         Claude    Ollama      multilingual   Haiku cleanup
         Vision    Vision      OCR            + confidence
              └──────┴──────────────┴───────────────┘
                     ▼
        structured JSON  { ..fields.., _confidence, _pages }
```

## Validation

Validated on **real, multilingual third-party invoices** (EN/FR/DE/NL, `invoice2data` test
set) — see [eval/EVAL_REAL.md](eval/EVAL_REAL.md). Route A (Claude Vision) and Route C
(Tesseract + LLM) both score **100%** on the fields each document carries; `/classify-image`
returns invoice 0.98–0.99. Reproduce with `bash eval/fetch_real_invoices.sh` then
`python eval/run_real_eval.py --route vision_premium`.

## Scope & Notes

- **Multi-page**: capped at `MAX_PDF_PAGES` (default 20) per document for cost/safety; raise it via env for long contracts. Vision pages are downscaled past `VISION_MAX_EDGE` px to bound token cost.
- **Handwriting**: handled by the vision routes (Route A is strongest). The pure-OCR route (Route C) is weaker on handwriting — use a vision route for handwritten docs.
- **Currencies**: ISO-4217 generic; EU decimal/comma and West-African FCFA (space-grouped, no decimal subunit → XOF/XAF) formats normalized. Ambiguous thousands/decimal separators on low-quality scans can still mislead the pure-OCR route.
- **Route C non-English**: install the matching Tesseract packs (`tesseract-ocr-fra/deu/nld/...`); falls back to English automatically if a pack is missing.

## Benchmark

A 500+ document, multi-type, multilingual benchmark (receipts, invoices, forms; including
multi-page and handwriting) is reproducible via `python eval/build_corpus.py` and scored with
`python eval/run_benchmark.py`. See [eval/BENCHMARK.md](eval/BENCHMARK.md) for results
(accuracy on the ground-truth subset + throughput/robustness at scale).

## License

MIT
