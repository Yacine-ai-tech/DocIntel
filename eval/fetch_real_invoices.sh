#!/bin/bash
# Fetch the real, multilingual sample invoices used by the real-doc eval and render page 1
# to PNG (the vision/OCR routes take images). Sources: invoice2data test set (MIT-licensed).
# The PDFs/PNGs are gitignored; this script makes the eval reproducible.
#
# Usage:  bash eval/fetch_real_invoices.sh   (needs: curl, pdftoppm/poppler-utils)
set -e
OUT="${1:-eval/real_invoices}"
BASE="https://raw.githubusercontent.com/invoice-x/invoice2data/master/tests/compare"
mkdir -p "$OUT"
for f in AmazonWebServices NetpresseInvoice QualityHosting free_fiber coolblue1 FlipkartInvoice; do
  curl -sL -o "$OUT/$f.pdf" "$BASE/$f.pdf"
  # render first page to PNG at 150 DPI (vision routes are first-page for multi-page PDFs)
  pdftoppm -png -r 150 -f 1 -l 1 "$OUT/$f.pdf" "$OUT/$f" >/dev/null 2>&1 || true
  # pdftoppm appends -1/-01 to the page; normalize to <name>.png
  for c in "$OUT/$f-1.png" "$OUT/$f-01.png"; do [ -f "$c" ] && mv "$c" "$OUT/$f.png"; done
  echo "fetched + rendered: $f"
done
echo "Done -> $OUT (PNG page-1 images for the real-doc eval)"
