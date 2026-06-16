"""Generate a realistic French-language invoice priced in West-African CFA francs (FCFA / XOF).

Public invoice datasets are EN/EU-centric and contain no FCFA documents, so we render one
deterministically to prove the pipeline reads French + the FCFA currency (spaces as thousands
separators, no decimal subunit, 18% TVA as used in the UEMOA zone). The PNG is reproducible
from this script, so it is gitignored; the ground truth (eval/fcfa_eval.jsonl) is committed.

Usage:  python eval/make_fcfa_sample.py        # -> eval/fcfa_sample/fcfa_invoice_fr.png
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "fcfa_sample"


def _font(size: int):
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    W, H = 1000, 1300
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    big, bold, reg, small = _font(40), _font(24), _font(22), _font(18)

    d.text((60, 50), "FACTURE", font=big, fill="black")
    d.text((60, 120), "TECHNOLOGIE DAKAR SARL", font=bold, fill="black")
    d.text((60, 155), "Sicap Liberté 6, Dakar, Sénégal", font=small, fill="black")
    d.text((60, 180), "NINEA : 005712345  -  RC : SN-DKR-2019-B-1234", font=small, fill="black")

    d.text((640, 120), "Facture N° : 2024-0042", font=reg, fill="black")
    d.text((640, 152), "Date : 15/03/2024", font=reg, fill="black")
    d.text((640, 184), "Échéance : 14/04/2024", font=reg, fill="black")

    d.text((60, 240), "Client : Ministère de l'Économie Numérique", font=reg, fill="black")

    y = 320
    d.rectangle([60, y, 940, y + 40], fill=(30, 30, 60))
    d.text((75, y + 8), "Désignation", font=reg, fill="white")
    d.text((640, y + 8), "Quantité", font=reg, fill="white")
    d.text((800, y + 8), "Montant", font=reg, fill="white")

    rows = [
        ("Développement application web", "1", "600 000"),
        ("Hébergement cloud (12 mois)", "1", "180 000"),
        ("Formation des agents (5 jours)", "1", "70 000"),
    ]
    y += 55
    for desc, qty, amt in rows:
        d.text((75, y), desc, font=reg, fill="black")
        d.text((670, y), qty, font=reg, fill="black")
        d.text((800, y), f"{amt} FCFA", font=reg, fill="black")
        y += 42

    y += 30
    d.text((640, y), "Sous-total :", font=reg, fill="black")
    d.text((800, y), "850 000 FCFA", font=reg, fill="black")
    d.text((640, y + 40), "TVA (18%) :", font=reg, fill="black")
    d.text((800, y + 40), "153 000 FCFA", font=reg, fill="black")
    d.text((640, y + 85), "Total TTC :", font=bold, fill="black")
    d.text((800, y + 85), "1 003 000 FCFA", font=bold, fill="black")

    d.text((60, H - 90), "Arrêtée la présente facture à la somme de un million trois mille",
           font=small, fill="black")
    d.text((60, H - 65), "francs CFA (1 003 000 FCFA). Merci de votre confiance.",
           font=small, fill="black")

    path = OUT / "fcfa_invoice_fr.png"
    img.save(path, "PNG")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
