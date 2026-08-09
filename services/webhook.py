"""
Outbound webhook delivery — used to notify external automation tools (n8n, Zapier,
Make, a plain HTTP endpoint, ...) when an async batch job finishes.

See docs/n8n/README.md for the n8n integration pattern (Webhook node receives the
payload this module sends).
"""
from __future__ import annotations

from typing import Any, Dict

from core.logger import get_logger

log = get_logger(__name__)

try:
    import httpx
    _HTTPX = True
except ImportError:
    _HTTPX = False
    log.warning("httpx not installed — webhook delivery disabled")

WEBHOOK_TIMEOUT_S = 15


async def send_webhook(url: str, payload: Dict[str, Any]) -> None:
    """
    POST `payload` as JSON to `url`. Best-effort: logs and swallows failures rather
    than raising, since a webhook delivery failure must never fail the job it's
    reporting on (the job already completed; results remain available via
    GET /batch/{job_id}/results regardless of webhook outcome).
    """
    if not url:
        return
    if not _HTTPX:
        log.warning("webhook to %s skipped — httpx not installed", url)
        return
    try:
        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT_S) as client:
            resp = await client.post(url, json=payload)
            log.info("webhook delivered to %s (status %d)", url, resp.status_code)
    except Exception as e:
        log.warning("webhook delivery to %s failed: %s", url, e)
