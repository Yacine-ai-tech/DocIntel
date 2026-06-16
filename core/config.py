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
    LLM_VISION_LOCAL = os.getenv("LLM_VISION_LOCAL", "ollama/llama3.2-vision")
    # Cheaper model for the OCR-route text→JSON cleanup (cost-optimized default).
    LLM_CLEANUP = os.getenv("LLM_CLEANUP", "anthropic/claude-haiku-4-5")

    # Multi-page handling: cap pages per document for cost/safety (vision is per-page).
    MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "20"))
    BATCH_MAX_CONCURRENCY = int(os.getenv("BATCH_MAX_CONCURRENCY", "8"))

    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    CORS_ALLOWED_ORIGINS = [
        o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8001").split(",")
        if o.strip()
    ]


settings = Settings()
