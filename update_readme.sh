cat << 'README_EOF' > /home/ai-sniper/Downloads/credential/DocIntel/README.md
# DocIntel

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![CI](https://github.com/Yacine-ai-tech/DocIntel/actions/workflows/ci.yml/badge.svg)](https://github.com/Yacine-ai-tech/DocIntel/actions/workflows/ci.yml)

**Research-Grade Document Intelligence Pipeline**

DocIntel is a production-ready, vision-first document extraction engine. It transforms unconstrained document modalities—including complex PDFs, scanned images, multi-column layouts, and handwritten forms—into high-fidelity, structured JSON. The architecture emphasizes latency-bounded inference, deterministic post-processing, and fallback safety via a cascaded extraction strategy.

> 🔗 **Live Demo:** [docintel.ysiddo-ai-projects.app/demo](https://docintel.ysiddo-ai-projects.app/demo)  
> *Self-hosting documentation:* see [SELF_HOSTING.md](SELF_HOSTING.md)

## Abstract & Capabilities

Modern document extraction is shifting from traditional multi-stage OCR pipelines (`Tesseract -> NLP -> JSON`) to vision-language models (VLMs) capable of end-to-end spatial and semantic reasoning. DocIntel implements this paradigm shift while maintaining legacy compliance paths.

- **Vision-First Cascaded Extraction:**
  - **Route A (Premium Cloud):** Leverages Claude Sonnet 4.6 Vision for state-of-the-art layout comprehension, handwritten transcription, and multilingual reasoning.
  - **Route B (Privacy-Preserving Local):** Operates entirely offline using Qwen2.5-VL 7B on accessible GPU hardware (e.g., NVIDIA T4) for zero API cost and stringent data sovereignty.
  - **Route C (Legacy Fallback):** Tesseract OCR coupled with an LLM text-cleanup phase.
- **Advanced Document Understanding:**
  - Direct integration with **Marker** for rigorous PDF-to-Markdown conversion.
  - Integration with **Surya** for layout-aware OCR and bounding-box resolution.
  - Zero-shot **`classify-image`** endpoint for robust object and document categorization.
- **Deterministic Normalization:** Multi-currency formatting (e.g., West African CFA franc `FCFA/XOF`), localized numeric parsing (EU comma vs US dot), and ISO-8601 date resolution.
- **Large Document Orchestration:** Implements map-reduce concurrency to ingest 100+ page documents seamlessly, evading contextual token limits.

## Benchmarks & Evaluation

DocIntel is continuously evaluated against real-world corpora to validate extraction fidelity across complex, noisy datasets.

- **Accuracy (Ground-Truth Subset):** 
  - **100% field-level accuracy** on real, multi-page, multilingual invoices (Route A & C).
  - **95.0% zero-shot accuracy** on the ICDAR-2019 SROIE standard benchmark (Task 3).
- **Scale & Robustness:** 100% successful ingestion across a 550-document evaluation suite, proving zero unhandled crashes on malformed inputs.
- Read the full research reports: [BENCHMARK.md](eval/BENCHMARK.md), [EVAL_REAL.md](eval/EVAL_REAL.md), and [SROIE_BENCHMARK.md](eval/SROIE_BENCHMARK.md).

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Configure applicable provider API keys
uvicorn api:app --port 8001
```

Access the drag-and-drop dashboard at `http://localhost:8001/demo`.

## System Architecture

```text
               ┌─────────────┐        PDFs → Render uniformly (pdf_to_pngs)
PDF / IMG ───► │   api.py    │ ───►   or fallback to raw text (extract_text_from_pdf)
               │   FastAPI   │               │
               └──────┬──────┘               ▼
                      │             ┌─────────────────┐
         Route ┌──────┼──────┐      │ Chunked Images  │
               ▼      ▼      ▼      └─────────────────┘
        Vision    Vision    OCR       ─► LLM Clean-up
       (Cloud)   (Local)   (Legacy)       (Text → JSON)
         │        │          │                 │
         └────────┴──────────┴─────────────────┘
                      ▼
               Structured JSON 
       { fields, _confidence, _pages, _tables }
```

## API Surface

| Method | Path                       | Function |
|--------|----------------------------|----------|
| POST   | `/process`                 | One-shot: Upload → Auto-classify → Multi-page Extract → JSON |
| POST   | `/extract`                 | Explicit extraction enforcing a specific route and schema |
| POST   | `/classify`                | Content-based document-type classification |
| POST   | `/classify-image`          | Vision-first object classification (e.g., for inventory) |
| POST   | `/extract/marker`          | Direct PDF to Markdown translation via Marker |
| POST   | `/extract/surya`           | Bounding-box and layout-aware extraction via Surya |
| POST   | `/extract-tables`          | Tabular extraction from PDFs using pdfplumber |
| POST   | `/batch/upload`            | Asynchronous batch job submission for high-volume processing |
| GET    | `/batch/{job_id}/results`  | Retrieve batch execution results |

## Enterprise Integration & Dual Licensing

DocIntel is released under the **AGPL-3.0 License**, ensuring unrestricted access for academic research and open-source application.

> **Commercial Usage:** Proprietary, closed-source deployments (including SaaS and internal enterprise tools) require a **Commercial License**. 
> Contact us to discuss commercial licensing, bespoke SLAs, and enterprise integration (SSO, strict RBAC, VPC constraints).

*Anonymous Telemetry:* We collect sparse, GDPR-compliant startup pings to gauge open-source utilization. Opt-out by setting `TELEMETRY_OPT_OUT=true` in your `.env`.

See [COMMERCIAL.md](COMMERCIAL.md) and [TELEMETRY.md](TELEMETRY.md) for details.
README_EOF
