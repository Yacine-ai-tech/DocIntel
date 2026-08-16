"""
Outbound webhook delivery — used to notify external automation tools (n8n, Zapier,
Make, a plain HTTP endpoint, ...) when an async batch job finishes.

See docs/n8n/README.md for the n8n integration pattern (Webhook node receives the
payload this module sends).
"""
from __future__ import annotations

import ipaddress
import socket
from typing import Any, Dict
from urllib.parse import urlparse

from core.logger import get_logger

log = get_logger(__name__)

try:
    import httpx
    _HTTPX = True
except ImportError:
    _HTTPX = False
    log.warning("httpx not installed — webhook delivery disabled")

WEBHOOK_TIMEOUT_S = 15


class WebhookURLRejected(ValueError):
    """Raised by _validate_webhook_url — caught at the call site so submission
    fails fast and visibly (400) instead of the job silently never notifying."""


def _validate_webhook_url(url: str) -> None:
    """Reject any webhook_url that could point at loopback, link-local (which
    includes cloud metadata endpoints — 169.254.169.254 on AWS/GCP/Azure/etc.),
    private (RFC1918), or multicast/reserved address space, and anything not
    plain https.

    webhook_url is client-supplied on an unauthenticated route (/batch/upload,
    /extract/text/batch — see the auth-bypass finding this pairs with) with no
    prior validation at all: the server would happily POST job results to
    whatever address a caller named, including internal-only infrastructure or
    a cloud metadata service. This is a blind SSRF (the response body isn't
    echoed back to the caller), which bounds — but doesn't eliminate — the
    risk: hitting a sensitive internal endpoint or being used as a DoS/attack
    relay against a third party are both still live with a blind response.

    Resolves the hostname and checks every returned address rather than just
    the hostname string, since "trusted-looking-name.attacker.com" resolving
    to 127.0.0.1 would otherwise sail through a naive string check.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise WebhookURLRejected(f"webhook_url must use https (got {parsed.scheme!r})")
    if not parsed.hostname:
        raise WebhookURLRejected("webhook_url has no host")

    try:
        addrs = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as e:
        raise WebhookURLRejected(f"webhook_url host could not be resolved: {e}") from e

    for family, _, _, _, sockaddr in addrs:
        ip = ipaddress.ip_address(sockaddr[0])
        is_non_public = (
            ip.is_private, ip.is_loopback, ip.is_link_local,
            ip.is_multicast, ip.is_reserved, ip.is_unspecified,
        )
        if any(is_non_public):
            raise WebhookURLRejected(
                f"webhook_url resolves to a non-public address ({ip}) — not allowed"
            )


async def send_webhook(url: str, payload: Dict[str, Any]) -> None:
    """
    POST `payload` as JSON to `url`. Best-effort: logs and swallows failures rather
    than raising, since a webhook delivery failure must never fail the job it's
    reporting on (the job already completed; results remain available via
    GET /batch/{job_id}/results regardless of webhook outcome).

    URL validation (_validate_webhook_url) is deliberately NOT done here — by
    the time a job completes and this fires from a background task, it's too
    late to usefully reject a bad URL back to the caller. Validate eagerly at
    submission time instead (see api.py's batch/webhook routes), so a bad
    webhook_url fails the request with a clear 400 up front rather than being
    silently swallowed by this function's own best-effort error handling.
    """
    if not url:
        return
    if not _HTTPX:
        log.warning("webhook to %s skipped — httpx not installed", url)
        return
    try:
        _validate_webhook_url(url)
    except WebhookURLRejected as e:
        log.warning("webhook to %s rejected at delivery time: %s", url, e)
        return
    try:
        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT_S, follow_redirects=False) as client:
            resp = await client.post(url, json=payload)
            log.info("webhook delivered to %s (status %d)", url, resp.status_code)
    except Exception as e:
        log.warning("webhook delivery to %s failed: %s", url, e)
