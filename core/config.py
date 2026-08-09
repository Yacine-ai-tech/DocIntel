"""
Slim DocIntel configuration — loads env vars for LLM routing and paths.
"""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
LOGS_DIR = BASE_DIR / "logs"

for _d in (UPLOADS_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


class Settings:
    """Centralized settings — read from environment with safe defaults."""

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    LOGS_DIR = str(LOGS_DIR)

    # ─── Route A: Claude Sonnet Vision (premium) ─────────────────────────────
    LLM_VISION_ROUTE_A = os.getenv("LLM_VISION_ROUTE_A", "anthropic/claude-sonnet-4-6")
    LLM_DEFAULT = os.getenv("LLM_DEFAULT", "groq/llama-3.3-70b-versatile")
    LLM_REASONING = os.getenv("LLM_REASONING", "anthropic/claude-sonnet-4-6")

    # ─── Route B: Ollama Vision (local / self-hosted only — never a third-party API) ──
    # Mode: "local" (Ollama on this machine/container) or "remote" (Ollama on hardware
    # you control elsewhere — LAN or reachable over the internet). Both modes talk to
    # an Ollama-compatible server you host yourself; Route B never calls Groq, HF, or
    # any other third-party inference provider.
    ROUTE_B_MODE = os.getenv("ROUTE_B_MODE", "local")

    # The Ollama model to use. Any Ollama vision model is supported.
    # Default: qwen2.5vl:7b (lighter, works on most GPUs)
    # Other good options: llama3.2-vision:11b (better quality, needs CUDA ≥ 7.5)
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5vl:7b")

    # If OLLAMA_MODEL fails due to GPU incompatibility (e.g. mllama runner on old cards),
    # automatically retry with this fallback model.
    OLLAMA_FALLBACK_MODEL = os.getenv("OLLAMA_FALLBACK_MODEL", "qwen2.5vl:7b")

    # --- LOCAL mode ---
    # Where your local Ollama instance is running.
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    # --- REMOTE mode ---
    # URL of an Ollama-compatible endpoint that YOU host — examples:
    #   Your own GPU rig/workstation on the LAN:    http://192.168.1.50:11434
    #   Your own GPU host, over the internet
    #     (via a tunnel/VPN):                       https://inference.your-domain.app
    #   Self-hosted Ollama on a VPS you rent:        http://1.2.3.4:11434
    ROUTE_B_REMOTE_ENDPOINT = os.getenv("ROUTE_B_REMOTE_ENDPOINT", "")

    # Bearer token for the remote endpoint — only needed if you've put your own auth
    # (e.g. a reverse proxy) in front of your self-hosted Ollama.
    ROUTE_B_REMOTE_TOKEN = os.getenv("ROUTE_B_REMOTE_TOKEN", "")

    # Optional: override the model tag sent to the remote endpoint, if your remote
    # Ollama instance uses a different tag name than OLLAMA_MODEL above.
    ROUTE_B_REMOTE_MODEL = os.getenv("ROUTE_B_REMOTE_MODEL", "")

    # Timeout in seconds for Route B inference calls.
    ROUTE_B_TIMEOUT = int(os.getenv("ROUTE_B_TIMEOUT", "60"))

    # Max concurrent Route B chunks when processing multi-page PDFs.
    # Keep at 1 (sequential) for local/single-GPU setups to avoid OOM.
    # Raise to 2-3 only for high-end remote endpoints.
    ROUTE_B_CHUNK_CONCURRENCY = int(os.getenv("ROUTE_B_CHUNK_CONCURRENCY", "1"))

    # ─── Route C: OCR fallback ────────────────────────────────────────────────
    # Cheaper model for the OCR-route text→JSON cleanup (cost-optimized default).
    LLM_CLEANUP = os.getenv("LLM_CLEANUP", "anthropic/claude-haiku-4-5")

    # ─── API Keys ─────────────────────────────────────────────────────────────
    # Required for Route A (Claude)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    # For LLM_DEFAULT text calls only — unrelated to Route B, which never uses these.
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    HF_TOKEN = os.getenv("HF_TOKEN", "")
    # Optional
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # ─── Multi-page handling ──────────────────────────────────────────────────
    MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "200"))
    BATCH_MAX_CONCURRENCY = int(os.getenv("BATCH_MAX_CONCURRENCY", "8"))

    CORS_ALLOWED_ORIGINS = [
        o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
        if o.strip()
    ]


settings = Settings()


# Gemini model fallback — when OPENAI_API_KEY is absent but GEMINI_API_KEY is
# present, any LLM model string referencing OpenAI/GPT is remapped to Gemini
# Flash automatically, requiring no code changes when switching providers.
def _apply_gemini_fallback():
    openai_key = getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    gemini_key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")

    if not openai_key and gemini_key:
        def fallback(model_str):
            if model_str and ("openai" in model_str.lower() or "gpt-" in model_str.lower()):
                return "gemini/gemini-2.5-flash"
            return model_str

        for attr in dir(settings):
            if attr.startswith("LLM_") and isinstance(getattr(settings, attr), str):
                setattr(settings, attr, fallback(getattr(settings, attr)))

        if hasattr(settings, "JUDGE_MODELS") and isinstance(settings.JUDGE_MODELS, list):
            settings.JUDGE_MODELS = [fallback(m) for m in settings.JUDGE_MODELS]

_apply_gemini_fallback()
