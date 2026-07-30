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


def _detect_dialect(endpoint: str) -> str:
    """Return 'groq', 'hf', or 'ollama' based on the endpoint URL."""
    ep = endpoint.lower()
    if "groq.com" in ep:
        return "groq"
    if "huggingface.co" in ep or "huggingface.cloud" in ep:
        return "hf"
    return "ollama"


def _resolve_model(ollama_tag: str, dialect: str) -> str:
    """
    Map an Ollama model tag to the model ID expected by the remote endpoint.
    Respects ROUTE_B_REMOTE_MODEL env override.
    """
    override = os.getenv("ROUTE_B_REMOTE_MODEL", "").strip()
    if override:
        return override
    if dialect == "groq":
        return _GROQ_MODEL_MAP.get(ollama_tag, ollama_tag)
    if dialect == "hf":
        return _HF_MODEL_MAP.get(ollama_tag, ollama_tag)
    # raw Ollama remote — use tag as-is (strip variant for cleaner Ollama API calls)
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
    Uses the /chat/completions format with base64 image_url.

    HuggingFace note: `hf-inference` provider was dropped for vision in mid-2025.
    Use ROUTE_B_HF_PROVIDER=nebius (default) or together/fireworks instead.
    The endpoint URL is rewritten to include the provider subdirectory automatically:
      https://router.huggingface.co/{provider}/models/{model}/v1/chat/completions
    """
    timeout = int(os.getenv("ROUTE_B_TIMEOUT", "60"))
    b64 = base64.b64encode(_downscale_image(imgs[0])).decode()

    # HF: rewrite endpoint to use the correct provider (nebius by default)
    # hf-inference dropped vision support — nebius/together/fireworks all work
    if dialect == "hf":
        hf_provider = os.getenv("ROUTE_B_HF_PROVIDER", "nebius").strip().lower()
        # Build correct HF router URL: /provider/models/{model}/v1/chat/completions
        url = f"https://router.huggingface.co/{hf_provider}/models/{model}/v1/chat/completions"
        log.info("Route B HF: using provider=%s model=%s", hf_provider, model)
    elif dialect == "groq":
        url = endpoint.rstrip("/") + "/chat/completions"
    else:
        url = endpoint.rstrip("/") + "/chat/completions"

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
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

    # Also check legacy env vars for Groq/HF tokens
    if not token:
        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        hf_key = os.getenv("HF_TOKEN", "").strip()
        if "groq.com" in endpoint.lower() and groq_key:
            token = groq_key
        elif "huggingface" in endpoint.lower() and hf_key:
            token = hf_key

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
