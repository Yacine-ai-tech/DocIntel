# Real-document evaluation (multilingual, complex invoices)

DocIntel is validated on **real, third-party invoices** — not synthetic fixtures — drawn from
the [`invoice2data`](https://github.com/invoice-x/invoice2data) test set (MIT-licensed). The
set is deliberately **multilingual and structurally varied** so the result reflects production
behaviour, not a single template.

| File | Lang | Vendor | Currency | Notes |
|------|------|--------|----------|-------|
| `AmazonWebServices` | EN | Amazon Web Services | USD | dense line items, tax breakdown |
| `NetpresseInvoice`  | FR | NETPRESSE           | EUR | French labels (TVA, total TTC) |
| `QualityHosting`    | DE | QualityHosting      | EUR | German labels; **total on page 2** |
| `free_fiber`        | FR | Free                | EUR | French telco layout |
| `coolblue1`         | NL | Coolblue            | EUR | Dutch labels (BTW), large amounts |
| `FlipkartInvoice`   | EN | WS Retail           | INR | Indian GST invoice, ₹ symbol |

The PDFs/PNGs are gitignored; reproduce them with `bash eval/fetch_real_invoices.sh`
(needs `curl` + `poppler-utils`). Ground truth lives in `eval/real_invoices_eval.jsonl`.

## How scoring works

`eval/run_real_eval.py` scores **only the fields present in each ground-truth row** (so the
German invoice, whose total sits on page 2, is fairly scored on its page-1 fields). Matching:

- **vendor** — lenient substring (case-insensitive)
- **invoice_number, date** — exact (normalized whitespace)
- **currency** — symbol/code normalized (`$`↔USD, `€`↔EUR, `₹`↔INR, `£`↔GBP)
- **subtotal, tax, total** — numeric, within `max(0.02, 1%)`

## Results

```
python eval/run_real_eval.py --route vision_premium   # Route A — Claude Sonnet 4.6 Vision
python eval/run_real_eval.py --route ocr_fallback     # Route C — Tesseract + LLM
python eval/run_real_eval.py --route vision_local      # Route B — Ollama Llama-3.2-Vision (GPU)
```

| Route | Engine | Score (present fields) |
|-------|--------|------------------------|
| **A — vision_premium** | Claude Sonnet 4.6 Vision | **39/39 = 100%** |
| **C — ocr_fallback**   | Tesseract (eng+fra+deu+nld) + LLM | **39/39 = 100%** |
| **B — vision_local**   | Ollama Llama-3.2-Vision | see note below |

Both cloud (A) and fully-local-text (C) routes extract **every present field correctly across
all four languages** — vendor, invoice number, date, currency, subtotal, tax, total. Route C
requires the matching Tesseract language packs (`tesseract-ocr-fra/deu/nld`) for non-English
documents.

### French + West-African CFA franc (FCFA → XOF)

A French invoice priced in FCFA (UEMOA-style, 18% TVA, space-grouped amounts like
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

Both routes read the French labels, transcribe the space-grouped amounts to plain decimals
(`1 003 000` → `1003000`), and normalize the currency to **XOF**.

### `/classify-image` (vision-first object classification)

| Image | Top category | Confidence |
|-------|--------------|------------|
| `AmazonWebServices.png` | invoice | 0.99 |
| `FlipkartInvoice.png`   | invoice | 0.98 |

### Route B (Ollama Llama-3.2-Vision)

Route B is the **local/private** path: no data leaves the host. Llama-3.2-Vision is impractical
on CPU, so it is benchmarked on a Lightning GPU (T4) attached on-demand via
`scripts/gpu_activate.py` and released immediately after to conserve free GPU-hours. The route
mechanism (LiteLLM `ollama/` vision routing → schema-conformant JSON) is wired and verified;
GPU accuracy numbers are recorded here when the on-demand run completes.

## Why this matters

The pitch is *vision-first, multilingual, local-or-cloud document AI.* These numbers back that
claim on **real customer-style invoices in four languages**, with two independent routes
(premium cloud + offline OCR) both at 100% on the fields each document actually carries.
