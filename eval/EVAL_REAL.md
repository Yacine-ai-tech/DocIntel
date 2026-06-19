# Real-Document Evaluation (multilingual, complex invoices)

DocIntel is evaluated on **real, third-party invoices** — not synthetic fixtures — drawn from the
[`invoice2data`](https://github.com/invoice-x/invoice2data) test set (MIT-licensed). The set is
deliberately multilingual and structurally varied so the results reflect production behaviour
rather than a single template.

| File | Lang | Vendor | Currency | Notes |
|------|------|--------|----------|-------|
| `AmazonWebServices` | EN | Amazon Web Services | USD | dense line items, tax breakdown |
| `NetpresseInvoice`  | FR | NETPRESSE           | EUR | French labels (TVA, total TTC) |
| `QualityHosting`    | DE | QualityHosting      | EUR | German labels; total on page 2 |
| `free_fiber`        | FR | Free                | EUR | French telecom layout |
| `coolblue1`         | NL | Coolblue            | EUR | Dutch labels (BTW), large amounts |
| `FlipkartInvoice`   | EN | WS Retail           | INR | Indian GST invoice, ₹ symbol |

The PDFs/PNGs are git-ignored; reproduce them with `bash eval/fetch_real_invoices.sh` (requires
`curl` and `poppler-utils`). Ground truth is in `eval/real_invoices_eval.jsonl`.

## Scoring methodology

`eval/run_real_eval.py` scores **only the fields present in each ground-truth record** (so the
German invoice, whose total is on page 2, is scored fairly on its page-1 fields). Matching:

- **vendor** — case-insensitive substring
- **invoice_number, date** — exact (whitespace-normalized)
- **currency** — symbol/code normalized (`$`↔USD, `€`↔EUR, `₹`↔INR, `£`↔GBP)
- **subtotal, tax, total** — numeric, within `max(0.02, 1%)`

## Results

```bash
python eval/run_real_eval.py --route vision_premium   # Route A — Claude Sonnet 4.6 Vision
python eval/run_real_eval.py --route ocr_fallback     # Route C — Tesseract + LLM
python eval/run_real_eval.py --route vision_local     # Route B — Ollama Qwen2.5-VL (GPU)
```

| Route | Engine | Score (present fields) |
|-------|--------|------------------------|
| **A — vision_premium** | Claude Sonnet 4.6 Vision | **39/39 = 100%** |
| **C — ocr_fallback**   | Tesseract (eng+fra+deu+nld) + LLM | **39/39 = 100%** |
| **B — vision_local**   | Ollama Qwen2.5-VL 7B (NVIDIA T4) | 25/39 = 64.1% (see note) |

Both the cloud (A) and fully-local-text (C) routes extract **every present field correctly across
all four languages** — vendor, invoice number, date, currency, subtotal, tax, total. Route C
requires the matching Tesseract language packs (`tesseract-ocr-fra/deu/nld`) for non-English
documents. Route B (a local 7B model) trails on the hardest multi-page layouts but excels on
receipts (see [BENCHMARK.md](BENCHMARK.md)).

### French + West-African CFA franc (FCFA → XOF)

A French invoice priced in FCFA (UEMOA convention, 18% TVA, space-grouped amounts such as
`1 003 000 FCFA`) — reproducible via `python eval/make_fcfa_sample.py`, ground truth in
`eval/fcfa_eval.jsonl`:

```bash
python eval/make_fcfa_sample.py
python eval/run_real_eval.py --dataset eval/fcfa_eval.jsonl --image-dir eval/fcfa_sample --route vision_premium
OCR_LANGS=fra+eng python eval/run_real_eval.py --dataset eval/fcfa_eval.jsonl --image-dir eval/fcfa_sample --route ocr_fallback
```

| Route | Engine | Score |
|-------|--------|-------|
| **A — vision_premium** | Claude Sonnet 4.6 Vision | **7/7 = 100%** |
| **C — ocr_fallback (fra+eng)** | Tesseract + LLM | **7/7 = 100%** |
| **B — vision_local** | Ollama Qwen2.5-VL 7B (NVIDIA T4) | **7/7 = 100%** |

All three routes read the French labels, transcribe the space-grouped amounts to plain decimals
(`1 003 000` → `1003000`), and normalize the currency to **XOF**.

### `/classify-image` (vision-first object classification)

| Image | Top category | Confidence |
|-------|--------------|------------|
| `AmazonWebServices.png` | invoice | 0.99 |
| `FlipkartInvoice.png`   | invoice | 0.98 |

### Route B — local vision model

Route B keeps all computation on the host (no data leaves the box). The 7B model is impractical on
CPU, so it is evaluated on an **NVIDIA T4 GPU** attached on demand and released after the run. The
validated model is **Ollama Qwen2.5-VL** (see the model note in [BENCHMARK.md](BENCHMARK.md); the
route is model-agnostic via `LLM_VISION_LOCAL`).

## Significance

These results substantiate the core claim — *vision-first, multilingual, local-or-cloud document
extraction* — on **real customer-style invoices in four languages**, with two independent routes
(premium cloud and offline OCR) each reaching 100% on the fields every document carries, and a
private local route that is competitive on receipts at zero per-page cost.
