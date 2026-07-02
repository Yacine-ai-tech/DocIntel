"""Best-effort Lightning Studio wake for Route B (local Ollama vision).

Route B runs the local vision model on an on-demand Lightning Studio reached through the
inference tunnel. When that Studio is asleep the vision call fails, so — instead of surfacing
a raw API error — the API triggers a wake here (non-blocking) and falls back to OCR for the
current request. A cold Studio takes ~1-2 min to boot, so the wake helps the *next* request.

Env: LIGHTNING_USER_ID, LIGHTNING_API_KEY, LIGHTNING_STUDIO_NAME (default 'upwork'),
LIGHTNING_TEAMSPACE, and LIGHTNING_ORG (org-owned teamspaces need `org`, not `user`).
"""
from __future__ import annotations

import os
import threading
from typing import Any, Dict

from core.logger import get_logger

log = get_logger(__name__)

_USER = os.environ.get("LIGHTNING_USER_ID")
_KEY = os.environ.get("LIGHTNING_API_KEY")
_NAME = os.environ.get("LIGHTNING_STUDIO_NAME", "upwork")
_TEAMSPACE = os.environ.get("LIGHTNING_TEAMSPACE", "hello-studio-setup-project")
_ORG = os.environ.get("LIGHTNING_ORG")  # e.g. yacinetrainer227-5z4m0-org

_waking = threading.Event()  # coalesce concurrent wake attempts


def _studio():
    from lightning_sdk import Studio
    # Org-owned teamspaces resolve via `org`; personal ones via `user`.
    if _ORG:
        return Studio(name=_NAME, teamspace=_TEAMSPACE, org=_ORG)
    return Studio(name=_NAME, teamspace=_TEAMSPACE, user=_USER)


def wake_studio() -> Dict[str, Any]:
    """Start the Studio if it isn't running. Blocking (used inside the background thread)."""
    if not _KEY or not (_USER or _ORG):
        return {"success": False, "error": "LIGHTNING creds not configured"}
    try:
        s = _studio()
        if "running" in str(s.status).lower():
            return {"success": True, "status": str(s.status), "message": "already running"}
        log.info("Route B: waking Lightning Studio %s…", _NAME)
        s.start()
        return {"success": True, "status": str(s.status), "message": "started"}
    except ImportError:
        return {"success": False, "error": "lightning-sdk not installed"}
    except Exception as e:  # creds/teamspace/network — never break the request path
        log.warning("Route B: studio wake failed: %s", e)
        return {"success": False, "error": str(e)[:200]}


def trigger_wake_async() -> bool:
    """Fire a wake in the background (non-blocking) so the request can fall back to OCR now.
    Returns True if a wake was actually initiated (creds present, not already waking)."""
    if not _KEY or not (_USER or _ORG):
        return False
    if _waking.is_set():
        return True  # a wake is already in flight
    _waking.set()

    def _go():
        try:
            wake_studio()
        finally:
            _waking.clear()

    threading.Thread(target=_go, daemon=True).start()
    return True
