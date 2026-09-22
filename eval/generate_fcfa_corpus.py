"""Generate a SYNTHETIC French-language, West-African CFA franc (FCFA/XOF) eval corpus.

Extends the single-document proof-of-concept in make_fcfa_sample.py into a real, scored
benchmark slice: N deterministic invoice + receipt PNGs, French field labels, FCFA
formatting (space-grouped thousands, no decimal subunit, 18% TVA per UEMOA convention),
with known ground truth in the same schema build_corpus.py writes — so this merges
directly into eval/benchmark/ground_truth.jsonl as a first-class, scored slice rather
than a one-off side sample.

Usage:
    python eval/generate_fcfa_corpus.py --n-invoices 25 --n-receipts 25 \
        --out eval/benchmark/images/fcfa --seed 42 >> eval/benchmark/ground_truth.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

VENDORS = [
    "Technologie Dakar SARL", "Abidjan Distribution SA", "Bamako Négoce",
    "Cotonou Import-Export", "Ouagadougou Matériaux", "Lomé Services Généraux",
    "Niamey Équipements", "Dakar Consulting Group", "Sénégal Bâtiment SARL",
    "Côte d'Ivoire Logistique", "Mali Fournitures Industrielles",
    "Burkina Agro-Business", "Togo Informatique SARL", "Bénin Textile SA",
]
CITIES = [
    ("Dakar", "Sénégal"), ("Abidjan", "Côte d'Ivoire"), ("Bamako", "Mali"),
    ("Cotonou", "Bénin"), ("Ouagadougou", "Burkina Faso"), ("Lomé", "Togo"),
    ("Niamey", "Niger"),
]
ITEMS = [
    "Développement application web", "Hébergement cloud (12 mois)",
    "Formation des agents", "Fournitures de bureau", "Matériel informatique",
    "Prestation de conseil", "Transport et logistique", "Maintenance annuelle",
    "Licence logicielle", "Câblage réseau", "Groupe électrogène",
    "Climatisation industrielle",
]
RECEIPT_ITEMS = [
    "Riz parfumé 25kg", "Huile végétale 5L", "Sucre en poudre 1kg",
    "Boissons gazeuses", "Savon de toilette", "Farine de blé 10kg",
    "Café soluble", "Lait en poudre", "Pâtes alimentaires", "Thé vert",
]
PAYMENT_METHODS = ["Espèces", "Mobile Money", "Carte bancaire", "Virement"]


def _font(size: int):
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _fmt_fcfa(n: int) -> str:
    """Space-grouped thousands, no decimal subunit — the real UEMOA convention this
    project's number-normalization rules (services/llm_extractor.py's _RULES) were
    extended to handle for FCFA specifically."""
    return f"{n:,}".replace(",", " ")


def _make_invoice(rng: random.Random, idx: int) -> dict:
    vendor = rng.choice(VENDORS)
    city, country = rng.choice(CITIES)
    inv_no = f"{rng.randint(2024, 2026)}-{rng.randint(1000, 9999):04d}"
    d0 = date(2026, 1, 1) + timedelta(days=rng.randint(0, 330))
    due = d0 + timedelta(days=rng.choice([15, 30, 45]))
    n_items = rng.randint(2, 4)
    rows, subtotal = [], 0
    for _ in range(n_items):
        desc = rng.choice(ITEMS)
        qty = rng.randint(1, 5)
        # Round to nearest 1000 FCFA — realistic quoting granularity in this market.
        unit = rng.randint(10, 600) * 1000
        line_total = qty * unit
        subtotal += line_total
        rows.append((desc, qty, unit, line_total))
    tva = round(subtotal * 0.18)
    total = subtotal + tva
    return {
        "file": f"fcfa_invoice_{idx:02d}.png", "doc_type": "invoice",
        "vendor": vendor, "city": city, "country": country, "invoice_number": inv_no,
        "date": d0.isoformat(), "due_date": due.isoformat(), "rows": rows,
        "subtotal": subtotal, "tax": tva, "total": total, "currency": "XOF",
    }


def _make_receipt(rng: random.Random, idx: int) -> dict:
    vendor = rng.choice(["Supermarché " + rng.choice(CITIES)[0], "Alimentation Générale",
                          "Boutique " + rng.choice(VENDORS).split()[0]])
    city, country = rng.choice(CITIES)
    d0 = date(2026, 1, 1) + timedelta(days=rng.randint(0, 330))
    n_items = rng.randint(2, 5)
    rows, total = [], 0
    for _ in range(n_items):
        name = rng.choice(RECEIPT_ITEMS)
        qty = rng.randint(1, 3)
        price = rng.randint(1, 20) * 500
        line_total = qty * price
        total += line_total
        rows.append((name, qty, price, line_total))
    return {
        "file": f"fcfa_receipt_{idx:02d}.png", "doc_type": "receipt",
        "vendor": vendor, "city": city, "country": country, "date": d0.isoformat(),
        "rows": rows, "total": total, "currency": "XOF",
        "payment_method": rng.choice(PAYMENT_METHODS),
    }


def _render_invoice(inv: dict, out_path: Path) -> None:
    W, H = 1000, 1300
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    big, bold, reg, small = _font(40), _font(24), _font(22), _font(18)

    d.text((60, 50), "FACTURE", font=big, fill="black")
    d.text((60, 120), inv["vendor"], font=bold, fill="black")
    d.text((60, 155), f"{inv['city']}, {inv['country']}", font=small, fill="black")
    d.text((60, 180), f"NINEA : {inv['invoice_number'][-6:]}345", font=small, fill="black")

    d.text((640, 120), f"Facture N° : {inv['invoice_number']}", font=reg, fill="black")
    d.text((640, 152), f"Date : {inv['date']}", font=reg, fill="black")
    d.text((640, 184), f"Échéance : {inv['due_date']}", font=reg, fill="black")

    y = 260
    d.rectangle([60, y, 940, y + 40], fill=(30, 30, 60))
    d.text((75, y + 8), "Désignation", font=reg, fill="white")
    d.text((580, y + 8), "Qté", font=reg, fill="white")
    d.text((680, y + 8), "P.U.", font=reg, fill="white")
    d.text((820, y + 8), "Montant", font=reg, fill="white")
    y += 55
    for desc, qty, unit, line_total in inv["rows"]:
        d.text((75, y), desc, font=reg, fill="black")
        d.text((590, y), str(qty), font=reg, fill="black")
        d.text((660, y), _fmt_fcfa(unit), font=reg, fill="black")
        d.text((800, y), f"{_fmt_fcfa(line_total)} FCFA", font=reg, fill="black")
        y += 42

    y += 30
    d.text((640, y), "Sous-total :", font=reg, fill="black")
    d.text((800, y), f"{_fmt_fcfa(inv['subtotal'])} FCFA", font=reg, fill="black")
    d.text((640, y + 40), "TVA (18%) :", font=reg, fill="black")
    d.text((800, y + 40), f"{_fmt_fcfa(inv['tax'])} FCFA", font=reg, fill="black")
    d.text((640, y + 85), "Total TTC :", font=bold, fill="black")
    d.text((800, y + 85), f"{_fmt_fcfa(inv['total'])} FCFA", font=bold, fill="black")
    d.text((60, H - 40), "SYNTHÉTIQUE — généré pour l'évaluation DocIntel", font=small, fill="#aaa")
    img.save(out_path)


def _render_receipt(r: dict, out_path: Path) -> None:
    W, H = 700, 1000
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    big, bold, reg, small = _font(30), _font(20), _font(18), _font(15)

    d.text((40, 40), r["vendor"], font=big, fill="black")
    d.text((40, 85), f"{r['city']}, {r['country']}", font=small, fill="black")
    d.text((40, 110), f"Date : {r['date']}", font=reg, fill="black")

    y = 160
    d.line([40, y, 660, y], fill="#999", width=1)
    y += 15
    for name, qty, price, line_total in r["rows"]:
        d.text((40, y), f"{name} x{qty}", font=reg, fill="black")
        d.text((480, y), f"{_fmt_fcfa(line_total)} FCFA", font=reg, fill="black")
        y += 34
    y += 10
    d.line([40, y, 660, y], fill="#999", width=1)
    y += 20
    d.text((40, y), "TOTAL", font=bold, fill="black")
    d.text((450, y), f"{_fmt_fcfa(r['total'])} FCFA", font=bold, fill="black")
    y += 50
    d.text((40, y), f"Paiement : {r['payment_method']}", font=reg, fill="black")
    d.text((40, H - 40), "SYNTHÉTIQUE — généré pour l'évaluation DocIntel", font=small, fill="#aaa")
    img.save(out_path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-invoices", type=int, default=25)
    ap.add_argument("--n-receipts", type=int, default=25)
    ap.add_argument("--out", default="eval/benchmark/images/fcfa")
    ap.add_argument("--ground-truth", default="eval/benchmark/ground_truth.jsonl",
                     help="Appended to, matching build_corpus.py's schema, unless --print-only")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--print-only", action="store_true",
                     help="Print JSONL lines to stdout instead of appending to --ground-truth")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = []
    for i in range(1, args.n_invoices + 1):
        inv = _make_invoice(rng, i)
        _render_invoice(inv, out_dir / inv["file"])
        lines.append(json.dumps({
            "file": f"fcfa/{inv['file']}", "doc_type": "invoice", "source": "synthetic_fcfa_fr",
            "pages": 1,
            "expected": {
                "vendor": inv["vendor"], "invoice_number": inv["invoice_number"],
                "date": inv["date"], "due_date": inv["due_date"], "currency": inv["currency"],
                "subtotal": inv["subtotal"], "tax": inv["tax"], "total": inv["total"],
            },
        }))
    for i in range(1, args.n_receipts + 1):
        r = _make_receipt(rng, i)
        _render_receipt(r, out_dir / r["file"])
        lines.append(json.dumps({
            "file": f"fcfa/{r['file']}", "doc_type": "receipt", "source": "synthetic_fcfa_fr",
            "pages": 1,
            "expected": {
                "merchant": r["vendor"], "date": r["date"], "total": r["total"],
                "currency": r["currency"], "payment_method": r["payment_method"],
            },
        }))

    if args.print_only:
        print("\n".join(lines))
    else:
        with open(args.ground_truth, "a") as f:
            f.write("\n".join(lines) + "\n")
    print(f"Generated {len(lines)} French/FCFA documents "
          f"({args.n_invoices} invoices, {args.n_receipts} receipts) in {out_dir}")


if __name__ == "__main__":
    main()
