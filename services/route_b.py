"""
DocIntel Route B — Ollama Vision Adapter
=========================================

Route B is strictly Ollama-based. Any vision-capable Ollama model works
(Qwen 2.5-VL, Llama 3.2 Vision, MiniCPM-V, etc.).

Two deployment modes, selected via ROUTE_B_MODE env var:

  local   — Ollama runs on the same machine or LAN (consumer GPU, workstation, server)
             Configure: OLLAMA_HOST (default http://localhost:11434)

  remote  — Ollama (or Ollama-compatible API) on a remote cloud endpoint
             Configure: ROUTE_B_REMOTE_ENDPOINT + ROUTE_B_REMOTE_TOKEN
             Supported dialects (auto-detected by endpoint URL):
               • Raw Ollama        → any server running Ollama (Lightning Studio, VPS, etc.)
               • Groq              → https://api.groq.com/openai/v1
               • HuggingFace       → https://router.huggingface.co/hf-inference

Model selection:
  OLLAMA_MODEL              — Ollama model tag (default: qwen2.5vl:7b)
  OLLAMA_FALLBACK_MODEL     — Retry with this if primary fails due to GPU incompatibility
  ROUTE_B_REMOTE_MODEL      — Override model ID for remote endpoint (bypasses auto-mapping)

GPU incompatibility handling:
  Llama 3.2 Vision uses the mllama runner which is not supported on all NVIDIA GPUs
  (requires compute capability ≥ 7.5). If Ollama returns an mllama-related error,
  DocIntel automatically retries with OLLAMA_FALLBACK_MODEL (default: qwen2.5vl:7b).
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import threading
import time
import urllib.request
from typing import List, Optional

log = logging.getLogger(__name__)

# ─── Built-in model name mapping table ────────────────────────────────────────
# Maps Ollama model tags → provider-specific model IDs for known remote dialects.
# Users can override entirely with ROUTE_B_REMOTE_MODEL.
#
# IMPORTANT — keep this table current:
#   Groq: llama-3.2 vision models were decommissioned July 2025.
#         Current vision model: llama-4-scout-17b-16e-instruct (supports image input)
#         Check https://console.groq.com/docs/deprecations for updates.
#   HF:   hf-inference provider does NOT support multimodal vision models as of July 2025.
#         If using HF, set ROUTE_B_REMOTE_MODEL to the exact HF model ID you want
#         (e.g. "Qwen/Qwen2.5-VL-7B-Instruct") and configure a provider that supports it
#         (nebius, together, etc.) via ROUTE_B_REMOTE_ENDPOINT.
_GROQ_MODEL_MAP: dict[str, str] = {
    # All Ollama vision tags → Groq's current vision model (llama-4-scout)
    "qwen2.5vl:7b":          "meta-llama/llama-4-scout-17b-16e-instruct",
    "qwen2.5vl:72b":         "meta-llama/llama-4-maverick-17b-128e-instruct",
    "llama3.2-vision":       "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama3.2-vision:11b":   "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama3.2-vision:90b":   "meta-llama/llama-4-maverick-17b-128e-instruct",
    "llava":                 "meta-llama/llama-4-scout-17b-16e-instruct",
    "minicpm-v":             "meta-llama/llama-4-scout-17b-16e-instruct",
}

_HF_MODEL_MAP: dict[str, str] = {
    # HF model IDs — user must also set ROUTE_B_REMOTE_ENDPOINT to a provider
    # that supports multimodal vision (hf-inference does NOT as of July 2025).
    "qwen2.5vl:7b":          "Qwen/Qwen2.5-VL-7B-Instruct",
    "qwen2.5vl:72b":         "Qwen/Qwen2.5-VL-72B-Instruct",
    "llama3.2-vision":       "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "llama3.2-vision:11b":   "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "llama3.2-vision:90b":   "meta-llama/Llama-3.2-90B-Vision-Instruct",
    "minicpm-v":             "openbmb/MiniCPM-V-2_6",
    "llava":                 "llava-hf/llava-1.5-7b-hf",
}

# GPU incompatibility: Ollama errors that indicate the model runner is unsupported
_MLLAMA_ERRORS = ("mllama", "not supported", "runner", "ggml_backend")

# Rate-limit the orchestrator wake signal (seconds between wake calls)
_LAST_WAKE = 0.0
_WAKE_MIN_INTERVAL = 90.0


# ─── Remote model name mapping ───────────────────────────────────────────────
# Groq: use their current vision model IDs
# HF Router: model IDs must match what each provider hosts
# Valid HF router providers (as of 2025): fireworks-ai, together, featherless-ai,
#   novita, nscale, deepinfra — use ROUTE_B_HF_PROVIDER to pick one.
# nebius was removed from HF router (no longer a valid provider).
_GROQ_MODEL_MAP: Dict[str, str] = {
    # Ollama tag → Groq model ID
    # CONFIRMED (2026-07-30): qwen/qwen3.6-27b is the working Groq vision model.
    # llama-4-scout deprecated 2026-07-17, llama-4-maverick deprecated 2026-03-09.
    # IMPORTANT: Groq vision requires PUBLIC HTTPS image URLs — base64 data URIs are rejected.
    # DocIntel must upload images to a temp public URL before sending to Groq vision.
    "qwen2.5vl:7b":         "qwen/qwen3.6-27b",
    "qwen2.5vl:72b":        "qwen/qwen3.6-27b",
    "qwen2-vl:7b":          "qwen/qwen3.6-27b",
    "llava:7b":             "qwen/qwen3.6-27b",
    "llava:13b":            "qwen/qwen3.6-27b",
    "llama3.2-vision:11b":  "qwen/qwen3.6-27b",
    "llama3.2-vision:90b":  "qwen/qwen3.6-27b",
    "default":              "qwen/qwen3.6-27b",  # always use qwen vision
}

# HF router provider → preferred vision model.
#
# NOTE: HF router vision requires a full-access HF token (not fine-grained).
# Fine-grained tokens return 400 errors from all supported providers
# (fireworks-ai, together, deepinfra) when calling vision models via
# router.huggingface.co.  To enable Route B with HF, supply a full-access
# token in ROUTE_B_HF_TOKEN, or set ROUTE_B_PROVIDER=ollama to use a
# locally-hosted Ollama vision model instead.  Without a full-access token,
# ROUTE_B_PROVIDER=hf will transparently fall through to Route C (Tesseract OCR).
_HF_PROVIDER_MODEL_MAP: Dict[str, str] = {
    "fireworks-ai": "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "together": "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "featherless-ai": "Qwen/Qwen2.5-VL-7B-Instruct",
    "novita": "Qwen/Qwen2.5-VL-7B-Instruct",
    "deepinfra": "Qwen/Qwen2.5-VL-7B-Instruct",
    "nscale": "Qwen/Qwen2.5-VL-7B-Instruct",
}

_MLLAMA_ERRORS = ("no such file", "not found", "mllama", "llama3.2 vision")




def _resolve_model(ollama_tag: str, dialect: str) -> str:
    """
    Map an Ollama model tag to the model ID expected by the remote endpoint.
    Respects ROUTE_B_REMOTE_MODEL env override.
    """
    override = os.getenv("ROUTE_B_REMOTE_MODEL", "").strip()
    if override:
        return override
    if dialect == "groq":
        mapped = _GROQ_MODEL_MAP.get(ollama_tag.lower())
        if not mapped:
            mapped = _GROQ_MODEL_MAP.get("default", "llama-3.3-70b-versatile")
        return mapped
    if dialect == "hf":
        provider = os.getenv("ROUTE_B_HF_PROVIDER", "fireworks-ai").strip().lower()
        return _HF_PROVIDER_MODEL_MAP.get(provider,
               "accounts/fireworks/models/llama-v3p2-11b-vision-instruct")
    # raw Ollama remote — use tag as-is
    return ollama_tag


def _fire_wake_signal() -> None:
    """
    Non-blocking background thread that pings the Orchestrator /wake endpoint.
    Only fires if ORCHESTRATOR_URL is set and enough time has passed since the last wake.
    This is optional — only needed for on-demand GPU servers (e.g. Lightning AI Studio).
    """
    global _LAST_WAKE
    url = os.getenv("ORCHESTRATOR_URL", "").strip()
    if not url:
        return
    now = time.time()
    if (now - _LAST_WAKE) < _WAKE_MIN_INTERVAL:
        return
    _LAST_WAKE = now

    def _go():
        try:
            h = {"Content-Type": "application/json",
                 "User-Agent": "DocIntel/2.0 Route-B"}
            tk = os.getenv("ORCH_TOKEN", "").strip()
            if tk:
                h["Authorization"] = f"Bearer {tk}"
            body = json.dumps({"gpu": True, "service": "docintel"}).encode()
            req = urllib.request.Request(
                url.rstrip("/") + "/wake", data=body, headers=h
            )
            urllib.request.urlopen(req, timeout=10)
            log.debug("Route B: Orchestrator wake signal sent to %s", url)
        except Exception as e:
            log.debug("Route B: wake signal failed (non-fatal): %s", e)

    threading.Thread(target=_go, daemon=True).start()


def _downscale_image(image_bytes: bytes, max_edge: int = 2200) -> bytes:
    """Shrink oversized images to reduce token cost. No-op without PIL."""
    try:
        from PIL import Image
        buf_in = io.BytesIO(image_bytes)
        img = Image.open(buf_in)
        if max(img.size) <= max_edge:
            return image_bytes
        ratio = max_edge / max(img.size)
        img = img.convert("RGB").resize(
            (int(img.width * ratio), int(img.height * ratio))
        )
        buf_out = io.BytesIO()
        img.save(buf_out, "PNG")
        return buf_out.getvalue()
    except Exception:
        return image_bytes


def _upload_temp_image(image_bytes: bytes) -> str:
    """
    Groq vision requires a public HTTPS URL and rejects base64 data URIs.
    This temporarily uploads the image to a free ephemeral host (uguu.se)
    so Groq can download it. Files auto-delete after 24h.
    """
    try:
        req = urllib.request.Request(
            "https://uguu.se/upload",
            data=b"".join([
                b"--boundary\r\n",
                b'Content-Disposition: form-data; name="files[]"; filename="image.png"\r\n',
                b"Content-Type: image/png\r\n\r\n",
                image_bytes,
                b"\r\n--boundary--\r\n"
            ]),
            headers={"Content-Type": "multipart/form-data; boundary=boundary"}
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        url = resp["files"][0]["url"]
        log.debug("Route B: Temp image uploaded to %s", url)
        return url
    except Exception as e:
        log.warning("Route B: Temp image upload failed: %s", e)
        raise ValueError("Groq vision requires a public image URL, but temp upload failed.") from e



# ─── Local mode ───────────────────────────────────────────────────────────────

def _call_local_sync(model: str, prompt: str, imgs: List[bytes]) -> str:
    """
    Talk directly to a local Ollama instance via its native /api/chat REST endpoint.
    Works for: consumer GPU, workstation, LAN server, Docker, etc.
    All Ollama vision models (Qwen2.5-VL, Llama 3.2 Vision, MiniCPM-V, ...) use
    the same payload format.
    """
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    timeout = int(os.getenv("ROUTE_B_TIMEOUT", "60"))

    # Build images list (base64-encoded, downscaled)
    images_b64 = [
        base64.b64encode(_downscale_image(img)).decode()
        for img in imgs
    ]

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": prompt,
            "images": images_b64,
        }],
        "stream": False,
        "options": {
            "num_ctx": int(os.getenv("OLLAMA_NUM_CTX", "8192")),
            "temperature": 0.1,
        },
    }

    body = json.dumps(payload).encode()
    h = {"Content-Type": "application/json",
         "User-Agent": "DocIntel/2.0 Route-B-Local"}
    req = urllib.request.Request(f"{host}/api/chat", data=body, headers=h)
    resp_raw = urllib.request.urlopen(req, timeout=timeout).read()
    resp = json.loads(resp_raw)
    return resp["message"]["content"]


async def _call_local(model: str, prompt: str, imgs: List[bytes]) -> str:
    """Async wrapper around the synchronous local Ollama call."""
    fallback_model = os.getenv("OLLAMA_FALLBACK_MODEL", "qwen2.5vl:7b")
    try:
        return await asyncio.to_thread(_call_local_sync, model, prompt, imgs)
    except Exception as e:
        err_str = str(e).lower()
        # GPU incompatibility: mllama runner not supported on this hardware
        if any(kw in err_str for kw in _MLLAMA_ERRORS) and fallback_model != model:
            log.warning(
                "Route B local: model %s failed with runner error (%s). "
                "Retrying with fallback model %s.", model, e, fallback_model
            )
            return await asyncio.to_thread(_call_local_sync, fallback_model, prompt, imgs)
        raise


# ─── Remote mode ──────────────────────────────────────────────────────────────

def _call_remote_ollama_sync(
    endpoint: str, model: str, prompt: str, imgs: List[bytes], token: str
) -> str:
    """
    Talk to a remote Ollama instance using Ollama's native /api/chat API.
    Used for: Lightning AI Studio (via cloudflared tunnel), self-hosted Ollama on VPS, etc.
    """
    timeout = int(os.getenv("ROUTE_B_TIMEOUT", "60"))
    images_b64 = [
        base64.b64encode(_downscale_image(img)).decode()
        for img in imgs
    ]
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": prompt,
            "images": images_b64,
        }],
        "stream": False,
        "options": {"num_ctx": int(os.getenv("OLLAMA_NUM_CTX", "8192")), "temperature": 0.1},
    }
    body = json.dumps(payload).encode()
    h = {"Content-Type": "application/json", "User-Agent": "DocIntel/2.0 Route-B-Remote"}
    if token:
        h["Authorization"] = f"Bearer {token}"

    # Try Ollama-native /api/chat first, then fall back to the inference_server /vision format
    url = endpoint.rstrip("/") + "/api/chat"
    try:
        req = urllib.request.Request(url, data=body, headers=h)
        resp = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        return resp["message"]["content"]
    except Exception:
        # Fall back to legacy inference_server /vision format (for older DocIntel deployments)
        url2 = endpoint.rstrip("/") + "/vision"
        legacy_payload = json.dumps({
            "image_b64": images_b64[0],
            "prompt": prompt,
            "model": model,
        }).encode()
        req2 = urllib.request.Request(url2, data=legacy_payload, headers=h)
        resp2 = json.loads(urllib.request.urlopen(req2, timeout=timeout).read())
        return resp2["content"]


def _call_remote_openai_sync(
    endpoint: str, model: str, prompt: str, imgs: List[bytes], token: str,
    dialect: str = "openai"
) -> str:
    """
    Talk to an OpenAI-compatible remote endpoint (Groq, HuggingFace, etc.).
    Uses the /chat/completions format with base64 image_url (or public URL for Groq).

    HuggingFace note: `hf-inference` dropped vision support. Use ROUTE_B_HF_PROVIDER
    (fireworks-ai by default) + a valid HF user access token (Bearer).
    Valid providers: fireworks-ai, together, featherless-ai, novita, deepinfra, nscale.
    URL is rewritten to:  https://router.huggingface.co/{provider}/v1/chat/completions
    """
    timeout = int(os.getenv("ROUTE_B_TIMEOUT", "60"))
    img_bytes = _downscale_image(imgs[0])

    # HF: rewrite endpoint to use the correct provider
    # Format: https://router.huggingface.co/{provider}/v1/chat/completions
    if dialect == "hf":
        hf_provider = os.getenv("ROUTE_B_HF_PROVIDER", "fireworks-ai").strip().lower()
        url = f"https://router.huggingface.co/{hf_provider}/v1/chat/completions"
        log.info("Route B HF: provider=%s model=%s", hf_provider, model)
        b64 = base64.b64encode(img_bytes).decode()
        image_content = {"url": f"data:image/png;base64,{b64}"}
    elif dialect == "groq":
        url = endpoint.rstrip("/") + "/chat/completions"
        # Groq rejects base64 data URIs. Upload temporarily to get a public URL.
        public_url = _upload_temp_image(img_bytes)
        image_content = {"url": public_url}
    else:
        url = endpoint.rstrip("/") + "/chat/completions"
        b64 = base64.b64encode(img_bytes).decode()
        image_content = {"url": f"data:image/png;base64,{b64}"}

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": image_content},
            ],
        }],
        "max_tokens": 2048,
    }

    body = json.dumps(payload).encode()
    h = {"Content-Type": "application/json", "User-Agent": "DocIntel/2.0 Route-B-Remote"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=h)
    resp = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    return resp["choices"][0]["message"]["content"]


async def _call_remote(model: str, prompt: str, imgs: List[bytes]) -> str:
    """
    Dispatch to the appropriate remote dialect (Groq, HF, or raw Ollama),
    including GPU fallback for mllama-incompatible hardware.
    """
    endpoint = os.getenv("ROUTE_B_REMOTE_ENDPOINT", "").strip()
    token = os.getenv("ROUTE_B_REMOTE_TOKEN", "").strip()

    # Token selection by dialect:
    # - Groq vision: GROQ_VISION_KEY (qwen/qwen3.6-27b account, confirmed working)
    #   fallback to GROQ_API_KEY if GROQ_VISION_KEY not set
    # - HF vision via router: HF_READ_TOKEN (full-access token, whoami-capable)
    #   HF_TOKEN (fine-grained) only works for embed/rerank, NOT for router vision
    # - Ollama remote: ROUTE_B_REMOTE_TOKEN or no auth
    if not token:
        if "groq.com" in endpoint.lower():
            token = (os.getenv("GROQ_VISION_KEY", "").strip()
                     or os.getenv("GROQ_API_KEY", "").strip())
        elif "huggingface" in endpoint.lower():
            token = (os.getenv("HF_READ_TOKEN", "").strip()
                     or os.getenv("HF_TOKEN", "").strip())

    dialect = _detect_dialect(endpoint)
    resolved_model = _resolve_model(model, dialect)
    fallback_model_tag = os.getenv("OLLAMA_FALLBACK_MODEL", "qwen2.5vl:7b")
    fallback_model = _resolve_model(fallback_model_tag, dialect)

    log.info("Route B remote: endpoint=%s dialect=%s model=%s", endpoint, dialect, resolved_model)

    if dialect in ("groq", "hf"):
        try:
            return await asyncio.to_thread(
                _call_remote_openai_sync, endpoint, resolved_model, prompt, imgs, token, dialect
            )
        except Exception as e:
            err_str = str(e).lower()
            if any(kw in err_str for kw in _MLLAMA_ERRORS) and fallback_model != resolved_model:
                log.warning("Route B remote: %s failed (%s), retrying with %s", resolved_model, e, fallback_model)
                return await asyncio.to_thread(
                    _call_remote_openai_sync, endpoint, fallback_model, prompt, imgs, token, dialect
                )
            raise
    else:
        # Raw Ollama (Lightning Studio, self-hosted, etc.)
        _fire_wake_signal()
        try:
            return await asyncio.to_thread(
                _call_remote_ollama_sync, endpoint, resolved_model, prompt, imgs, token
            )
        except Exception as e:
            err_str = str(e).lower()
            if any(kw in err_str for kw in _MLLAMA_ERRORS) and fallback_model != resolved_model:
                log.warning("Route B remote: %s failed (%s), retrying with %s", resolved_model, e, fallback_model)
                return await asyncio.to_thread(
                    _call_remote_ollama_sync, endpoint, fallback_model, prompt, imgs, token
                )
            raise


# ─── Public API ───────────────────────────────────────────────────────────────

async def call_route_b(prompt: str, imgs: List[bytes]) -> str:
    """
    Main entry point for Route B inference.

    Reads ROUTE_B_MODE to decide local vs remote, then delegates.
    Raises on failure so the caller (vision_extractor) can fall through to Route C.

    Args:
        prompt: The extraction prompt (from VISION_PROMPTS + _RULES).
        imgs:   List of page image bytes (PNG). Typically 1-2 pages per call.

    Returns:
        Raw text response from the model (may or may not be valid JSON — caller handles parse).
    """
    mode = os.getenv("ROUTE_B_MODE", "local").strip().lower()
    model = os.getenv("OLLAMA_MODEL", "qwen2.5vl:7b").strip()

    if mode == "remote":
        endpoint = os.getenv("ROUTE_B_REMOTE_ENDPOINT", "").strip()
        if not endpoint:
            raise ValueError(
                "ROUTE_B_MODE=remote but ROUTE_B_REMOTE_ENDPOINT is not set. "
                "Set it to your Ollama endpoint URL (e.g. https://api.groq.com/openai/v1)."
            )
        return await _call_remote(model, prompt, imgs)
    else:
        # local (default)
        return await _call_local(model, prompt, imgs)
