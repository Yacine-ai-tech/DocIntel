# DocIntel Architecture

How DocIntel turns documents into structured, normalised data. This page complements
[`README.md`](README.md) (what it is and how to run it), [`RESEARCH.md`](RESEARCH.md) (the
reasoning behind the routes) and [`BENCHMARK.md`](BENCHMARK.md) (measured accuracy). An interactive
version is in the application under **Architecture**.

## 1. System overview

```
 PDF · scan · phone photo ─▶ preprocess ─▶ route ─┬─ A  Claude Vision ──────────┐
                                                  ├─ B  Ollama vision (own HW) ─┼─▶ merge pages
                                                  └─ C  OCR + LLM cleanup ──────┘     │
                                                       (Surya or Tesseract)           ▼
                                                                          deterministic normalisation
                                                                          amounts · currencies · dates
                                                                                      ▼
                                                                    JSON · library · webhook · batch
```

## 2. Routes

| Route | Engine | Strength | Cost |
|---|---|---|---|
| A `vision_route_a` | frontier vision model | complex, handwritten or mixed-language layouts | per page |
| B `vision_route_b` | an Ollama vision model on hardware you control | privacy and zero per-page cost | your hardware |
| C `ocr_fallback` | OCR engine, then a small LLM to structure the text | speed and low cost | lowest |

Route C's OCR engine is a deployment choice: Surya (layout-aware) when `SURYA_ENABLED=true`,
Tesseract when it is `false`. The engine never switches at run time: a Surya failure is an error
(HTTP 503), not a silent downgrade. Routes A and B fall back to Route C when they fail and use the
configured engine. If Route B is not available on a host, requests for it are processed by Route C
and flagged as such.

## 3. Components

| Component | Role |
|---|---|
| Preprocessing | deskew, contrast and size normalisation of images and rendered pages |
| Chunked map-reduce | large documents are processed in page chunks and merged by type-agnostic rules |
| LLM structuring | doc-type prompts turn OCR text into typed fields |
| Normalisation | locale-aware amounts, ISO currency codes (including FCFA/XOF), ISO 8601 dates; unparseable values are left untouched |
| Batch processor | concurrent jobs with a retention period |
| Camera pairing | QR pairing so a phone can upload scans to a session |
| Library | extracted documents, scoped to the session, in Postgres or local files |
| Webhooks | optional delivery of results to another system |

## 4. Life of a document

1. **Admit**: authenticate, check size and page limits.
2. **Resolve the route**: explicit choice, default, or the mobile default for camera uploads.
3. **Prepare**: render PDF pages (large PDFs can be rendered on a separate host) and preprocess.
4. **Extract**: vision routes in chunks, or OCR then structuring.
5. **Merge and normalise**: lists concatenate in page order, totals take the last page's value,
   header scalars the first page's, confidence the minimum; then deterministic cleaning.
6. **Deadline**: a time limit returns the best partial result rather than failing.
7. **Persist and deliver**: library entry, optional webhook, response with fields, route and flags.

## 5. Design decisions

| Decision | Reason |
|---|---|
| Three routes, chosen explicitly | cost, privacy and accuracy trade off differently per document |
| Engine fixed by configuration | a silent engine switch would change accuracy without telling anyone |
| Normalise deterministically | language models are unreliable at locale-specific numbers and dates |
| Merge rules independent of document type | large documents work without per-type code |
| Conservative normaliser | it can improve the output but never lose information |
| Result cache for identical pages | repeated scans return at once |
| Readiness separate from liveness | the OCR engine is warm before traffic arrives |

## 6. Interfaces

| Route | Purpose |
|---|---|
| `POST /process`, `/process/async`, `/extract` | extraction (synchronous or job) |
| `POST /extract/text`, `/extract/marker`, `/extract-fields`, `/extract-llm`, `/extract-tables` | focused extraction modes |
| `POST /classify`, `/classify-image` | document and image classification |
| `POST /batch/upload`, `GET /batch/{id}`, `/batch/{id}/results` | batch |
| `POST /camera/pair`, `GET /camera/*` | mobile capture |
| `GET /api/documents*`, `DELETE /api/documents*` | library |
| `GET /health`, `GET /ready`, `GET /benchmarks` | liveness, readiness, published figures |

## 7. Configuration

Everything is environment-driven; [`.env.example`](.env.example) lists every variable with its
purpose. Groups: routes and models, OCR engine, limits and timeouts, storage, access, camera and
batch retention, telemetry.

## 8. Startup and readiness

On start the OCR engine is loaded and a short page is processed in the background. `GET /ready`
returns 503 until that completes; route traffic only after it returns 200. The first page that has
not been seen before takes longer than a repeated one.

## 9. Privacy

An optional startup ping carries only service name, version and a random installation id; disable
it with `TELEMETRY_OPT_OUT=true` or `DO_NOT_TRACK=1`. Documents and extracted values are never part
of telemetry.
