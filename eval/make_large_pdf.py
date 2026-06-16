"""Generate a large multi-page PDF (default 120 pages) with a real text layer, to prove the
100+ page pipeline end-to-end. The header (vendor / invoice number / date) is on page 1 and
the **grand total is only on the LAST page** — so a correct extraction must aggregate across
all chunks (header = first-wins, total = last-wins in services/doc_merge.py).

Output: eval/large_doc/large_invoice_<N>p.pdf  (gitignored, reproducible)
Ground truth printed + written to eval/large_doc/large_eval.jsonl.

Usage:  python eval/make_large_pdf.py --pages 120
Needs:  fpdf2  (pip install fpdf2)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "large_doc"

VENDOR = "Sahel Logistics & Freight SARL"
INVOICE_NO = "INV-2026-LARGE-0001"
DATE = "2026-03-15"
CURRENCY = "USD"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=120)
    a = ap.parse_args()
    from fpdf import FPDF  # fpdf2

    OUT.mkdir(parents=True, exist_ok=True)
    n = a.pages
    line_total = 100.0
    subtotal = round(line_total * (n - 2), 2)  # one line item on each filler page
    tax = round(subtotal * 0.10, 2)
    total = round(subtotal + tax, 2)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Page 1 — header
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "COMMERCIAL INVOICE", ln=True)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"Vendor: {VENDOR}", ln=True)
    pdf.cell(0, 8, f"Invoice Number: {INVOICE_NO}", ln=True)
    pdf.cell(0, 8, f"Date: {DATE}", ln=True)
    pdf.cell(0, 8, f"Currency: {CURRENCY}", ln=True)
    pdf.cell(0, 8, "Line items continue on the following pages.", ln=True)

    # Filler pages — one line item each (forces multi-chunk processing)
    for i in range(2, n):
        pdf.add_page()
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 8, f"Page {i} of {n}", ln=True)
        pdf.cell(0, 8, f"Item {i - 1}: Freight handling service - qty 1 - {line_total:.2f} {CURRENCY}",
                 ln=True)

    # Last page — totals only here
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "SUMMARY (final page)", ln=True)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"Subtotal: {subtotal:.2f} {CURRENCY}", ln=True)
    pdf.cell(0, 8, f"Tax (10%): {tax:.2f} {CURRENCY}", ln=True)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"TOTAL: {total:.2f} {CURRENCY}", ln=True)

    out_pdf = OUT / f"large_invoice_{n}p.pdf"
    pdf.output(str(out_pdf))

    gt = {"file": out_pdf.name, "pages": n, "doc_type": "invoice",
          "expected": {"vendor": VENDOR, "invoice_number": INVOICE_NO, "date": DATE,
                       "currency": CURRENCY, "subtotal": subtotal, "tax": tax, "total": total}}
    (OUT / "large_eval.jsonl").write_text(json.dumps(gt) + "\n")
    print(f"wrote {out_pdf} ({n} pages)")
    print(f"ground truth: {json.dumps(gt['expected'])}")


if __name__ == "__main__":
    main()
