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

    LLM_DEFAULT = os.getenv("LLM_DEFAULT", "groq/llama-3.3-70b-versatile")
    LLM_REASONING = os.getenv("LLM_REASONING", "anthropic/claude-sonnet-4-6")
    LLM_VISION_PREMIUM = os.getenv("LLM_VISION_PREMIUM", "anthropic/claude-sonnet-4-6")
    # Route B local vision. Default = qwen2.5vl:7b — the validated model that runs on the on-demand
    # T4 GPU. (Llama 3.2 Vision is the strategy's listed alternative, but its `mllama` arch needs an
    # mllama-capable runner — older Ollama (~0.11.x) or vLLM — so it isn't the default on Ollama
    # 0.30.x.) Model is swappable per box via LLM_VISION_LOCAL (e.g. ollama/llama3.2-vision, gemma).
    LLM_VISION_LOCAL = os.getenv("LLM_VISION_LOCAL", "ollama/qwen2.5vl:7b")
    # Cheaper model for the OCR-route text→JSON cleanup (cost-optimized default).
    LLM_CLEANUP = os.getenv("LLM_CLEANUP", "anthropic/claude-haiku-4-5")

    # Multi-page handling: cap pages per document for cost/safety. Large docs are processed in
    # page-chunks and merged (map-reduce), so 100+ page PDFs are supported up to this ceiling.
    MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "200"))
    BATCH_MAX_CONCURRENCY = int(os.getenv("BATCH_MAX_CONCURRENCY", "8"))

    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    CORS_ALLOWED_ORIGINS = [
        o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
        if o.strip()
    ]


settings = Settings()


# --- OPENAI TO GEMINI FALLBACK LOGIC ---
def _apply_gemini_fallback():
    openai_key = getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    gemini_key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    
    if not openai_key and gemini_key:
        def fallback(model_str):
            if model_str and ("openai" in model_str.lower() or "gpt-" in model_str.lower()):
                return "gemini/gemini-1.5-flash"
            return model_str
            
        for attr in dir(settings):
            if attr.startswith("LLM_") and isinstance(getattr(settings, attr), str):
                setattr(settings, attr, fallback(getattr(settings, attr)))
        
        if hasattr(settings, "JUDGE_MODELS") and isinstance(settings.JUDGE_MODELS, list):
            settings.JUDGE_MODELS = [fallback(m) for m in settings.JUDGE_MODELS]

_apply_gemini_fallback()
