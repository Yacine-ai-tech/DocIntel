"""
Structured logging for the entire platform.

Usage::

    from core.logger import get_logger
    log = get_logger(__name__)
    log.info("Server started on port %d", port)
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from core.config import settings

_LOG_DIR = Path(settings.LOGS_DIR)
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "app.log"

_configured = False


def _configure_once() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    fmt = logging.Formatter(settings.LOG_FORMAT)

    # Console handler
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    # File handler
    fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Suppress noisy third-party loggers
    for noisy in ("httpx", "httpcore", "chromadb", "sentence_transformers", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger; auto-configures on first call."""
    _configure_once()
    return logging.getLogger(name)
