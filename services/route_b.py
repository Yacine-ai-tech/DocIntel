"""
DocIntel Route B — Ollama Vision Adapter
=========================================

Route B is strictly Ollama, and strictly your own hardware. It never talks to a
third-party inference provider (no Groq, no Hugging Face router, no other hosted
API) — that's what makes it the "private / $0-per-page" route. Any vision-capable
Ollama model works (Qwen 2.5-VL, Llama 3.2 Vision, MiniCPM-V, etc.).

Two deployment modes, selected via ROUTE_B_MODE env var — both talk to Ollama's
native /api/chat protocol, the only difference is *where* that Ollama instance runs:

  local   — Ollama runs on the same machine/container as the DocIntel app.
             Configure: OLLAMA_HOST (default http://localhost:11434)

  remote  — Ollama (or an Ollama-API-compatible server) runs on hardware you
             control elsewhere — a home GPU rig, a workstation on your LAN, a
             box you rent and self-host Ollama on, etc. Same protocol as local,
             just reachable over the network (LAN or over the internet via a
             tunnel/VPN/public IP) instead of localhost.
             Configure: ROUTE_B_REMOTE_ENDPOINT (+ optional ROUTE_B_REMOTE_TOKEN
             if you've put auth in front of your own endpoint).

Model selection:
  OLLAMA_MODEL              — Ollama model tag (default: qwen2.5vl:7b)
  OLLAMA_FALLBACK_MODEL     — Retry with this if primary fails due to GPU incompatibility
  ROUTE_B_REMOTE_MODEL      — Override the model tag sent to the remote endpoint, if it
                               differs from your local naming (still just an Ollama tag).

GPU incompatibility handling:
  Llama 3.2 Vision uses the mllama runner which is not supported on all NVIDIA GPUs
  (requires compute capability >= 7.5). If Ollama returns an mllama-related error,
  DocIntel automatically retries with OLLAMA_FALLBACK_MODEL (default: qwen2.5vl:7b).
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import urllib.request
from typing import List

log = logging.getLogger(__name__)

# Ollama errors that indicate the model runner is unsupported on this GPU.
_MLLAMA_ERRORS = ("no such file", "not found", "mllama", "llama3.2 vision",
                   "not supported", "runner", "ggml_backend")


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


def _ollama_chat_sync(
    host: str, model: str, prompt: str, imgs: List[bytes], timeout: int, token: str = ""
) -> str:
    """
    Talk to an Ollama instance via its native /api/chat REST endpoint. Used for both
    local (localhost/LAN) and remote (self-hosted, reachable over the network) modes —
    the protocol is identical, only the host differs.
    """
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
    h = {"Content-Type": "application/json", "User-Agent": "DocIntel/2.0 Route-B"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{host.rstrip('/')}/api/chat", data=body, headers=h)
    resp_raw = urllib.request.urlopen(req, timeout=timeout).read()
    resp = json.loads(resp_raw)
    return resp["message"]["content"]


async def _call_local(model: str, prompt: str, imgs: List[bytes]) -> str:
    """Ollama on this machine/LAN (OLLAMA_HOST, default http://localhost:11434)."""
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    timeout = int(os.getenv("ROUTE_B_TIMEOUT", "60"))
    fallback_model = os.getenv("OLLAMA_FALLBACK_MODEL", "qwen2.5vl:7b")
    try:
        return await asyncio.to_thread(_ollama_chat_sync, host, model, prompt, imgs, timeout)
    except Exception as e:
        err_str = str(e).lower()
        if any(kw in err_str for kw in _MLLAMA_ERRORS) and fallback_model != model:
            log.warning(
                "Route B local: model %s failed with runner error (%s). "
                "Retrying with fallback model %s.", model, e, fallback_model
            )
            return await asyncio.to_thread(_ollama_chat_sync, host, fallback_model, prompt, imgs, timeout)
        raise


async def _call_remote(model: str, prompt: str, imgs: List[bytes]) -> str:
    """
    Ollama on hardware you control elsewhere (ROUTE_B_REMOTE_ENDPOINT) — same protocol
    as local, just over the network. Optional ROUTE_B_REMOTE_TOKEN if you've put your
    own auth in front of it (e.g. a reverse proxy). Never a third-party inference API.
    """
    endpoint = os.getenv("ROUTE_B_REMOTE_ENDPOINT", "").strip()
    token = os.getenv("ROUTE_B_REMOTE_TOKEN", "").strip()
    timeout = int(os.getenv("ROUTE_B_TIMEOUT", "60"))
    model = os.getenv("ROUTE_B_REMOTE_MODEL", "").strip() or model
    fallback_model = os.getenv("OLLAMA_FALLBACK_MODEL", "qwen2.5vl:7b")

    log.info("Route B remote: endpoint=%s model=%s", endpoint, model)
    try:
        return await asyncio.to_thread(_ollama_chat_sync, endpoint, model, prompt, imgs, timeout, token)
    except Exception as e:
        err_str = str(e).lower()
        if any(kw in err_str for kw in _MLLAMA_ERRORS) and fallback_model != model:
            log.warning("Route B remote: %s failed (%s), retrying with %s", model, e, fallback_model)
            return await asyncio.to_thread(
                _ollama_chat_sync, endpoint, fallback_model, prompt, imgs, timeout, token
            )
        raise


# ─── Public API ───────────────────────────────────────────────────────────────

async def call_route_b(prompt: str, imgs: List[bytes]) -> str:
    """
    Main entry point for Route B inference.

    Reads ROUTE_B_MODE to decide local vs remote, then delegates. Both modes talk to
    an Ollama-compatible server you host yourself — Route B never calls a third-party
    inference provider. Raises on failure so the caller (vision_extractor) can fall
    through to Route C.

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
                "Point it at your own Ollama-compatible inference host, e.g. "
                "http://192.168.1.50:11434 (LAN) or https://inference.your-domain.app "
                "(your own hardware, reachable over the internet via a tunnel/VPN)."
            )
        return await _call_remote(model, prompt, imgs)
    else:
        # local (default)
        return await _call_local(model, prompt, imgs)
