"""Image pre-processing shared by Route B (VLM) and Route C (OCR) extraction.

Two independent fixes, each targeting a specific measured failure mode:

- ``deskew_image``: Radon-transform skew correction for Route B. Open-weight 7B VLMs
  (qwen2.5-vl) lose token resolution on dense multi-column tables when the source photo
  is rotated even a few degrees off axis — the model has to spend attention on
  re-aligning text before it can read it. Finds the rotation angle that maximizes the
  variance of the horizontal projection profile (text lines are sharpest, i.e. highest
  variance, when perfectly horizontal) and rotates to correct it.

- ``enhance_contrast_for_ocr``: CLAHE + Otsu binarization for Route C. Raw Tesseract
  collapses on crumpled paper, uneven lighting, and low-contrast phone photos. CLAHE
  (contrast-limited adaptive histogram equalization) normalizes local contrast per
  region instead of globally, so a photo with both a shadowed and a lit half doesn't
  wash out one of them; Otsu's method then picks a per-image binarization threshold
  instead of a fixed one, producing a clean black-text-on-white-background image
  Tesseract was designed for.

Both are no-ops (return the input unchanged) on any failure — extraction must never
break because pre-processing had a problem on some edge-case image.
"""
from __future__ import annotations

import io
import logging

log = logging.getLogger(__name__)

try:
    import numpy as np
    from PIL import Image
    from skimage.filters import threshold_otsu
    from skimage.exposure import equalize_adapthist
    from skimage.transform import radon, rotate
    from skimage.color import rgb2gray
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def _to_gray_array(image_bytes: bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.asarray(img) / 255.0
    return img, rgb2gray(arr)


def _estimate_skew_angle(gray, max_angle: float = 15.0, step: float = 0.5) -> float:
    """Radon transform over a small angle window around vertical; the angle whose
    projection has the highest variance is the one where text lines are most sharply
    aligned (peaked profile = horizontal text), so that's the deskew angle.
    Restricted to +/-max_angle since real scanned/photographed documents are only ever
    slightly off-axis — a wider search risks "correcting" toward a wrong 90-degree-ish
    local optimum on table-heavy layouts."""
    # Downsample for speed — skew angle doesn't need full resolution to estimate.
    h, w = gray.shape
    scale = 400 / max(h, w) if max(h, w) > 400 else 1.0
    small = gray if scale == 1.0 else np.asarray(
        Image.fromarray((gray * 255).astype("uint8")).resize(
            (max(1, int(w * scale)), max(1, int(h * scale)))
        )
    ) / 255.0

    angles = np.arange(90 - max_angle, 90 + max_angle + step, step)
    sinogram = radon(small, theta=angles, circle=False)
    variances = sinogram.var(axis=0)
    best_angle = angles[int(np.argmax(variances))]
    return best_angle - 90.0  # degrees of rotation needed to correct


def deskew_image(image_bytes: bytes) -> bytes:
    """Detect and correct small rotation skew before Route B VLM tiling. Returns the
    original bytes unchanged if skimage/numpy aren't installed or anything fails."""
    if not _AVAILABLE:
        return image_bytes
    try:
        img, gray = _to_gray_array(image_bytes)
        angle = _estimate_skew_angle(gray)
        if abs(angle) < 0.3:  # not worth rotating — avoids resampling blur on already-straight scans
            return image_bytes
        # Negated: skimage.transform.rotate's positive-angle direction is opposite the
        # sign convention _estimate_skew_angle returns (verified empirically — applying
        # `angle` directly doubles the skew instead of canceling it).
        rotated = rotate(np.asarray(img) / 255.0, -angle, resize=True, mode="edge")
        out_img = Image.fromarray((rotated * 255).astype("uint8"))
        buf = io.BytesIO()
        out_img.save(buf, "PNG")
        return buf.getvalue()
    except Exception as e:
        log.warning("deskew failed (%s) — using original image", e)
        return image_bytes


def enhance_contrast_for_ocr(image_bytes: bytes) -> bytes:
    """CLAHE local-contrast normalization + Otsu binarization before Tesseract. Returns
    the original bytes unchanged if skimage/numpy aren't installed or anything fails."""
    if not _AVAILABLE:
        return image_bytes
    try:
        _, gray = _to_gray_array(image_bytes)
        equalized = equalize_adapthist(gray, clip_limit=0.03)
        thresh = threshold_otsu(equalized)
        binary = (equalized > thresh).astype("uint8") * 255
        out_img = Image.fromarray(binary, mode="L")
        buf = io.BytesIO()
        out_img.save(buf, "PNG")
        return buf.getvalue()
    except Exception as e:
        log.warning("contrast enhancement failed (%s) — using original image", e)
        return image_bytes
