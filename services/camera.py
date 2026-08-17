"""
Camera integration — live feed, mobile pairing, QR scanning.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timedelta, timezone

from core import db
from core.config import settings
from core.logger import get_logger

log = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


try:
    import cv2
    _CV2 = True
except ImportError:
    _CV2 = False

try:
    import qrcode
    _QR = True
except ImportError:
    _QR = False

# How long a pairing session (and its persisted state) stays around after
# creation. Matches the session's own 24h expiry, plus slack so an expired-
# but-recently-active session's last result is still visible for a short
# window after expiry, rather than vanishing at the exact same moment.
SESSION_TTL_SECONDS = int(os.getenv("CAMERA_SESSION_TTL_SECONDS", str(48 * 3600)))

_STATE_DIR = Path(settings.LOGS_DIR) / "camera_sessions"


def _session_to_json(session: Dict[str, Any]) -> Dict[str, Any]:
    """datetime fields aren't JSON-serializable — convert to ISO strings for
    persistence only; the in-memory copy keeps real datetime objects."""
    out = dict(session)
    for k in ("created_at", "expires_at", "last_upload"):
        v = out.get(k)
        out[k] = v.isoformat() if isinstance(v, datetime) else v
    return out


def _session_from_json(data: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(data)
    for k in ("created_at", "expires_at", "last_upload"):
        v = out.get(k)
        out[k] = datetime.fromisoformat(v) if isinstance(v, str) else v
    return out


@dataclass
class MobilePairing:
    """Pair mobile devices for remote document capture.

    Session state is persisted to LOGS_DIR/camera_sessions/*.json on every
    change and reloaded on startup, with TTL-based eviction on every new
    session creation. Previously state lived only in the in-memory _sessions
    dict: a process restart silently dropped every pairing (a paired phone
    mid-scan would find its token suddenly invalid with no explanation), and
    expired sessions were never actually removed — validate() only flipped
    active=False, leaving the dict entry (and, before this, nothing on disk to
    even worry about) growing unbounded for the process's lifetime.
    """
    _sessions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _token_lock = threading.Lock()

    def __post_init__(self):
        if db.DB_ENABLED:
            try:
                db.ensure_schema()
            except Exception as e:
                # Same reasoning as BatchProcessor.__init__: this runs at module
                # import time, so an unhandled exception here crashed the whole
                # app on any Postgres connectivity hiccup, not just camera
                # pairing. Falls back to disk persistence, consistent with
                # core.db's own "optional" contract.
                log.error("Postgres unavailable at startup (%s) — falling back to disk persistence for camera sessions", e)
                _STATE_DIR.mkdir(parents=True, exist_ok=True)
        else:
            _STATE_DIR.mkdir(parents=True, exist_ok=True)
        self._load_persisted_sessions()

    def _session_path(self, token: str) -> Path:
        return _STATE_DIR / f"{token}.json"

    def _persist(self, token: str) -> None:
        """Best-effort: a persistence failure must never break pairing itself."""
        session = self._sessions.get(token)
        if session is None:
            return
        try:
            if db.DB_ENABLED:
                # psycopg handles native datetime -> TIMESTAMPTZ directly — no ISO
                # string conversion needed here (that's only for the JSON file path).
                db.upsert_camera_session(token, session)
            else:
                self._session_path(token).write_text(json.dumps(_session_to_json(session)))
        except Exception as e:
            log.warning("failed to persist camera session %s…: %s", token[:8], e)

    def _load_persisted_sessions(self) -> None:
        if db.DB_ENABLED:
            try:
                self._sessions.update(db.load_all_camera_sessions())
            except Exception as e:
                log.warning("failed to load persisted camera sessions from Postgres: %s", e)
        else:
            if not _STATE_DIR.exists():
                return
            for f in _STATE_DIR.glob("*.json"):
                try:
                    data = json.loads(f.read_text())
                    token = f.stem
                    self._sessions[token] = _session_from_json(data)
                except Exception as e:
                    log.warning("failed to load persisted camera session from %s: %s", f, e)
        self._evict_expired()

    def _evict_expired(self) -> None:
        cutoff = _utcnow() - timedelta(seconds=SESSION_TTL_SECONDS)
        expired = [t for t, s in self._sessions.items() if s.get("created_at", _utcnow()) < cutoff]
        for token in expired:
            self._sessions.pop(token, None)
            try:
                if db.DB_ENABLED:
                    db.delete_camera_session(token)
                else:
                    self._session_path(token).unlink(missing_ok=True)
            except Exception as e:
                log.warning("failed to evict persisted camera session %s…: %s", token[:8], e)

    def create_session(self, user: str, device_name: str = "Mobile Device") -> str:
        """Create a new pairing session with expiry."""
        self._evict_expired()
        token = secrets.token_urlsafe(16)
        with self._token_lock:
            self._sessions[token] = {
                "user": user,
                "device_name": device_name,
                "created_at": _utcnow(),
                "expires_at": _utcnow() + timedelta(hours=24),
                "uploads": 0,
                "last_upload": None,
                "last_result": None,
                "active": True,
            }
        self._persist(token)
        log.info("Mobile session for %s on %s (token=%s…)", user, device_name, token[:8])
        return token

    def validate(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate token and check expiry."""
        with self._token_lock:
            session = self._sessions.get(token)
            if not session:
                return None
            if _utcnow() > session["expires_at"]:
                session["active"] = False
                log.info("Token expired: %s…", token[:8])
                self._persist(token)
                return None
            if not session["active"]:
                return None
        return session

    def record_upload(self, token: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """Record a successful upload for this token, storing the extraction result
        (if given) so the desktop session that generated the QR can poll for it."""
        with self._token_lock:
            session = self._sessions.get(token)
            if session and session["active"]:
                session["uploads"] += 1
                session["last_upload"] = _utcnow()
                if result is not None:
                    session["last_result"] = result
                self._persist(token)
                return True
        return False

    def get_status(self, token: str) -> Optional[Dict[str, Any]]:
        """Poll target for the desktop side: session state + the most recent upload's
        result, if any. Does not require re-validating expiry the way validate() does
        (an expired session can still be polled to show its last result)."""
        with self._token_lock:
            session = self._sessions.get(token)
            if not session:
                return None
            return {
                "active": session["active"] and _utcnow() <= session["expires_at"],
                "uploads": session["uploads"],
                "last_upload": session["last_upload"].isoformat() if session["last_upload"] else None,
                "last_result": session.get("last_result"),
            }

    def qr_bytes(self, token: str) -> Optional[bytes]:
        """Generate QR code for pairing token."""
        if not _QR:
            return None
        import io
        # FRONTEND_URL is the only reliable source here — the backend can't know its own
        # public-facing origin (behind a proxy/tunnel, different host than the frontend in
        # split deployments, etc.). Falls back to localhost:8001 for local single-container
        # dev — deliberately NOT a live hosted URL: for anyone self-hosting, defaulting to
        # this project's own public demo would silently send their users' camera-pairing QR
        # codes to someone else's frontend/backend pair (a confusing, broken pairing attempt
        # dressed up as a working QR code) instead of failing obviously. See SELF_HOSTING.md —
        # this is the one env var every split frontend/backend deployment must set correctly.
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8001").rstrip("/")
        url = f"{frontend_url}/camera/mobile?token={token}"
        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.getvalue()

    def qr_base64(self, token: str) -> Optional[str]:
        """Generate QR code as base64 data URI."""
        qr_bytes = self.qr_bytes(token)
        if not qr_bytes:
            return None
        return f"data:image/png;base64,{base64.b64encode(qr_bytes).decode('utf-8')}"


class CameraManager:
    """Manage live camera feed and document scanning."""

    def __init__(self):
        self._cap = None
        self._running = False
        self.pairing = MobilePairing()

    # ---- live feed --------------------------------------------------------

    def start(self, device: int = 0) -> bool:
        if not _CV2:
            log.error("OpenCV not available")
            return False
        self._cap = cv2.VideoCapture(device)
        if not self._cap.isOpened():
            log.error("Cannot open camera %s", device)
            return False
        self._running = True
        log.info("Camera %s started", device)
        return True

    def read_frame(self):
        if self._cap and self._running:
            ok, frame = self._cap.read()
            return frame if ok else None
        return None

    def stop(self):
        self._running = False
        if self._cap:
            self._cap.release()
            self._cap = None
            log.info("Camera stopped")

    # ---- pairing helpers --------------------------------------------------
    # list_mobile_sessions/revoke_mobile_session (and MobilePairing.list_sessions/
    # revoke underneath them) were removed here — dead code, unreachable from any
    # route. If a sessions-list/revoke route is ever added, note that `user` is
    # entirely self-declared by the caller (/camera/pair's `user` form field,
    # defaulting to "demo_user") with no real authentication tying it to an
    # identity — wiring either of those up naively would let anyone list or
    # revoke another user's sessions by guessing/reusing their `user` string.
    # Don't reintroduce them without real auth alongside.

    def pair_mobile(self, user: str, device_name: str = "Mobile Device") -> Dict[str, Any]:
        """Create pairing session and return token + QR code."""
        token = self.pairing.create_session(user, device_name)
        qr_b64 = self.pairing.qr_base64(token)
        return {
            "token": token,
            "qr_available": qr_b64 is not None,
            "qr_code": qr_b64,
            "expires_in_hours": 24,
            "frontend_url": os.getenv("FRONTEND_URL", "http://localhost:8001").rstrip("/"),
        }

    def validate_mobile(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate pairing token (includes session metadata)."""
        return self.pairing.validate(token)

    def get_mobile_status(self, token: str) -> Optional[Dict[str, Any]]:
        """Poll target for the desktop dashboard: has this token's phone uploaded yet,
        and if so, what did extraction return."""
        return self.pairing.get_status(token)

    def record_mobile_upload(self, token: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """Record successful upload from paired device, with its extraction result."""
        return self.pairing.record_upload(token, result)
