# GAP_REPORT — DocIntel (redesign v2, Session A — 2026-07-06)

## 1. API inventory (api.py, verified)

| Route | Purpose | Response notes |
|---|---|---|
| `GET /health` | liveness | `{status, service, version}` |
| `POST /classify` | doc-type classification (content + filename heuristic) | `ProcessResponse{doc_type, route:"classify", confidence}` |
| `POST /classify-image` (file, categories csv) | vision object classification | `{category, confidence 0-1, reasoning, processing_time_ms}` (`{error}` on failure) |
| `POST /extract` (file, route, doc_type) | extraction on a chosen route | `ProcessResponse` |
| `POST /process` (file, route, doc_type="auto") | one-shot: auto-classify → multi-page extract → tables count | `ProcessResponse`; fields may carry `_confidence`, `_fallback_from`, `_note`, `_studio_waking`, `_tables_detected`, `_ocr_chars` |
| `POST /extract-llm` (text, doc_type) | Route C text→JSON | `ProcessResponse` |
| `POST /extract-tables` (file) | pdfplumber tables | `{tables[], table_count}` |
| `POST /batch/upload` (files[], route, doc_type) | background batch | `{job_id, total}` |
| `GET /batch/{id}` | job status | `{id, status, total, processed, failed, ...}` |
| `GET /batch/{id}/results` | job results | `{job_id, results:[{filename, fields, confidence, page_count}]}` |
| `GET /` | serves demo/index.html | to be switched to `frontend/dist` (additive fallback kept) |
| `/demo` mount | old static demo | kept |

Routes: `vision_premium` = anthropic/claude-sonnet-4-6 · `vision_local` = ollama/qwen2.5vl:7b
(on-demand Studio; API degrades to OCR with `_note`/`_studio_waking` when asleep) ·
`ocr_fallback` = Tesseract + claude-haiku-4-5 cleanup. (core/config.py verified.)

## 2. P0 screen mapping

| Screen | Element | Status |
|---|---|---|
| Workspace | upload → `POST /process`; route/doc_type pickers | supported |
| Workspace | pipeline stages animation | supported-with-caveat: no per-stage timing in response → indeterminate stage progress while awaiting; completion states filled from real fields (`route`, `doc_type`, `confidence`, `_fallback_from`, `_tables_detected`, `page_count`, `processing_time_ms`) |
| Workspace | routing visualization incl. fallback | supported (`route` + `_fallback_from` + `_note`) |
| Workspace | extraction field cards, editable, copy, JSON toggle, export | supported (client-side over `fields`) |
| Image Intelligence | `POST /classify-image` preview/category/confidence/reasoning | supported. Suggested tags/metadata: **cut** (API returns none) |
| Batch | upload, poll status, results table | supported |
| Benchmarks | stat wall + route comparison charts | supported as static FACTS from eval/BENCHMARK.md (see §4) |

## 3. Approved minor extensions

**None required.** Backend untouched except the additive SPA-serving change in `api.py`
(root handler prefers `frontend/dist/index.html`; `/assets` mount + GET catch-all registered last).

## 4. Verified claims (from eval/BENCHMARK.md + SROIE_BENCHMARK.md — use THESE, not v1 prompt numbers)

- Scale: **550/550 = 100%** ingestion success, 0 unhandled errors.
- Route A (Claude Sonnet 4.6 Vision): invoices **39/39 = 100%** (multilingual, multi-page); receipts (CORD) **37/40 = 92.5%**.
- Route B (qwen2.5-VL 7B, T4): receipts **77/100 = 77.0%**; invoices **25/39 = 64.1%**; French+FCFA **7/7 = 100%**.
- Route C (Tesseract+LLM): clean invoices **100%**; CORD receipts **57/200 = 28.5%**.
- FCFA/XOF French invoice: **7/7 = 100%** on Routes A and C.
- SROIE Task-3 zero-shot: **95.0%** overall (company 95 / date 90 / total 100).

## 5. Real-vs-Demo table (filled in Session B)

| Screen | Element | Source |
|---|---|---|
| Workspace | whole flow | real (`/process`) |
| Image Intelligence | whole flow | real (`/classify-image`) |
| Batch | whole flow | real (`/batch/*`) |
| Benchmarks | numbers/charts | factual static (cited to eval/BENCHMARK.md) |
| Vision Models (P1) | route cards | factual static (core/config.py) |
| Activity (P1) | timeline | real, session-local (localStorage) |
