"""Generate a SYNTHETIC invoice eval corpus (clearly labeled synthetic).

Renders N deterministic, realistic-looking invoice PNGs with known ground truth, and writes
the matching label file the eval harness reads. This is a stand-in for a hand-labeled set of
real invoices — accuracy numbers measured against it are honest for *synthetic* documents.

Usage:
    python eval/generate_synthetic.py --n 50 --out eval/synthetic_invoices --labels eval/invoices_eval.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

VENDORS = [
    "Acme Industrial Supply", "Northwind Logistics", "Globex Manufacturing",
    "Initech Software", "Umbrella Components", "Stark Materials", "Wayne Freight",
    "Soylent Foods", "Hooli Cloud Services", "Vandelay Imports", "Wonka Packaging",
    "Cyberdyne Systems", "Pied Piper Data", "Gekko Capital Tools", "Tyrell Optics",
    "Massive Dynamic", "Aperture Fabrication", "Black Mesa Lab Supply",
]
ITEMS = [
    "Steel brackets", "Hydraulic hose", "Cloud compute hours", "Consulting (hrs)",
    "Packaging units", "Freight surcharge", "Safety gloves", "Lubricant 5L",
    "Sensor module", "Cable assembly", "Maintenance plan", "License seat",
]
CURRENCIES = ["USD", "EUR", "GBP"]
SYMBOL = {"USD": "$", "EUR": "€", "GBP": "£"}


def _font(size: int):
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                import logging; logging.error('Unhandled exception', exc_info=True)
                pass
    return ImageFont.load_default()


def _make_invoice(rng: random.Random, idx: int) -> dict:
    vendor = rng.choice(VENDORS)
    cur = rng.choice(CURRENCIES)
    sym = SYMBOL[cur]
    inv_no = f"INV-{rng.randint(2024, 2026)}-{rng.randint(1000, 9999)}"
    d0 = date(2026, 1, 1) + timedelta(days=rng.randint(0, 330))
    due = d0 + timedelta(days=rng.choice([14, 30, 45, 60]))
    n_items = rng.randint(2, 5)
    line_items, subtotal = [], 0.0
    for _ in range(n_items):
        desc = rng.choice(ITEMS)
        qty = rng.randint(1, 40)
        unit = round(rng.uniform(5, 950), 2)
        lt = round(qty * unit, 2)
        subtotal += lt
        line_items.append({"description": desc, "quantity": qty, "unit_price": unit, "total": round(lt, 2)})
    subtotal = round(subtotal, 2)
    tax_rate = rng.choice([0.0, 0.05, 0.08, 0.10, 0.20])
    tax = round(subtotal * tax_rate, 2)
    total = round(subtotal + tax, 2)
    return {
        "file": f"inv_{idx:02d}.png",
        "vendor": vendor, "invoice_number": inv_no, "currency": cur, "symbol": sym,
        "date": d0.isoformat(), "due_date": due.isoformat(),
        "line_items": line_items, "subtotal": subtotal, "tax": tax, "total": total,
    }


def _render(inv: dict, out_path: Path) -> None:
    W, H = 1000, 1400
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    big, h2, body, small = _font(46), _font(26), _font(22), _font(18)
    d.text((60, 50), "INVOICE", font=big, fill="black")
    d.text((60, 120), inv["vendor"], font=h2, fill="black")
    d.text((60, 160), "123 Commerce Way, Industry City", font=small, fill="#333")
    d.text((640, 130), f"Invoice #: {inv['invoice_number']}", font=body, fill="black")
    d.text((640, 165), f"Date: {inv['date']}", font=body, fill="black")
    d.text((640, 200), f"Due: {inv['due_date']}", font=body, fill="black")
    d.text((640, 235), f"Currency: {inv['currency']}", font=body, fill="black")
    # table header
    y = 320
    d.rectangle([60, y, 940, y + 36], fill="#eef2ff")
    d.text((70, y + 6), "Description", font=body, fill="black")
    d.text((520, y + 6), "Qty", font=body, fill="black")
    d.text((620, y + 6), "Unit", font=body, fill="black")
    d.text((800, y + 6), "Amount", font=body, fill="black")
    y += 50
    sym = inv["symbol"]
    for li in inv["line_items"]:
        d.text((70, y), li["description"], font=body, fill="black")
        d.text((520, y), str(li["quantity"]), font=body, fill="black")
        d.text((620, y), f"{sym}{li['unit_price']:,.2f}", font=body, fill="black")
        d.text((800, y), f"{sym}{li['total']:,.2f}", font=body, fill="black")
        y += 40
    y += 20
    d.line([600, y, 940, y], fill="#999", width=1)
    y += 14
    d.text((620, y), "Subtotal:", font=body, fill="black"); d.text((800, y), f"{sym}{inv['subtotal']:,.2f}", font=body, fill="black"); y += 36
    d.text((620, y), "Tax:", font=body, fill="black"); d.text((800, y), f"{sym}{inv['tax']:,.2f}", font=body, fill="black"); y += 36
    d.text((620, y), "TOTAL:", font=h2, fill="black"); d.text((800, y), f"{sym}{inv['total']:,.2f}", font=h2, fill="black")
    d.text((60, H - 60), "SYNTHETIC — generated for DocIntel eval", font=small, fill="#aaa")
    img.save(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--out", default="eval/synthetic_invoices")
    ap.add_argument("--labels", default="eval/invoices_eval.jsonl")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    label_lines = []
    for i in range(1, args.n + 1):
        inv = _make_invoice(rng, i)
        _render(inv, out_dir / inv["file"])
        label_lines.append(json.dumps({
            "file": inv["file"],
            "expected": {
                "vendor": inv["vendor"], "invoice_number": inv["invoice_number"],
                "date": inv["date"], "currency": inv["currency"],
                "subtotal": inv["subtotal"], "tax": inv["tax"], "total": inv["total"],
            },
        }))
    Path(args.labels).write_text("\n".join(label_lines) + "\n")
    print(f"Generated {args.n} synthetic invoices in {out_dir} + labels {args.labels}")


if __name__ == "__main__":
    main()
