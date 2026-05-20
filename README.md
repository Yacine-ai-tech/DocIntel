# DocIntel

**Vision-first document AI. Drop a PDF or image, get structured JSON in under 2 seconds. Local or cloud.**

## What It Does

- **3 extraction routes**: Claude Sonnet 4.6 Vision (premium), Ollama Llama 3.2 Vision (local/private), Tesseract+LLM (fallback)
- **Doc-type-aware schemas**: invoice, contract, receipt, financial_report, auction_listing
- **`/classify-image` endpoint**: vision-first object classification for auction/inventory aggregation
- **Batch processing** with background jobs and status tracking
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
| POST   | /classify                  | Fast doc-type classification                  |
| POST   | /classify-image            | Vision-first object classification            |
| POST   | /extract                   | Full extraction (file + route + doc_type)     |
| POST   | /extract-llm               | LLM extract from raw text                     |
| POST   | /extract-tables            | PDF tables via pdfplumber                     |
| POST   | /batch/upload              | Start background batch job                    |
| GET    | /batch/{job_id}            | Job status                                    |
| GET    | /batch/{job_id}/results    | Job results                                   |

## Architecture

```
        ┌─────────────┐
PDF/IMG │   api.py    │
   ────►│  FastAPI    │
        └──────┬──────┘
               │
       ┌───────┼───────┐
       │       │       │
       ▼       ▼       ▼
  vision_   marker_   llm_
  extractor extractor extractor
  (premium  (PDF→MD)  (OCR text
   / local)           → JSON)
```

## Known Limitations

- Handwritten invoices: not supported (use external OCR)
- Multi-page PDFs: first page only for vision routes
- Foreign currencies: USD/EUR/GBP/JPY supported; others may need config

## License

MIT
