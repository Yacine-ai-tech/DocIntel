"""
Camera integration — live feed, mobile pairing, QR scanning.
"""
from __future__ import annotations

import json
import secrets
import threading
import base64
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta

from core.config import settings
from core.logger import get_logger

log = get_logger(__name__)

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


@dataclass
class MobilePairing:
    """Pair mobile devices for remote document capture."""
    _sessions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _token_lock = threading.Lock()

    def create_session(self, user: str, device_name: str = "Mobile Device") -> str:
        """Create a new pairing session with expiry."""
        token = secrets.token_urlsafe(16)
        with self._token_lock:
            self._sessions[token] = {
                "user": user,
                "device_name": device_name,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(hours=24),
                "uploads": 0,
                "last_upload": None,
                "active": True,
            }
        log.info("Mobile session for %s on %s (token=%s…)", user, device_name, token[:8])
        return token

    def validate(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate token and check expiry."""
        with self._token_lock:
            session = self._sessions.get(token)
            if not session:
                return None
            if datetime.utcnow() > session["expires_at"]:
                session["active"] = False
                log.info("Token expired: %s…", token[:8])
                return None
            if not session["active"]:
                return None
        return session

    def record_upload(self, token: str) -> bool:
        """Record a successful upload for this token."""
        with self._token_lock:
            session = self._sessions.get(token)
            if session and session["active"]:
                session["uploads"] += 1
                session["last_upload"] = datetime.utcnow()
                return True
        return False

    def revoke(self, token: str) -> bool:
        """Revoke a pairing token."""
        with self._token_lock:
            session = self._sessions.get(token)
            if session:
                session["active"] = False
                log.info("Token revoked: %s…", token[:8])
                return True
        return False

    def list_sessions(self, user: str) -> List[Dict[str, Any]]:
        """List all active sessions for a user."""
        with self._token_lock:
            return [
                {
                    "token": token[:8] + "...",
                    "device_name": s["device_name"],
                    "created_at": s["created_at"].isoformat(),
                    "expires_at": s["expires_at"].isoformat(),
                    "uploads": s["uploads"],
                    "last_upload": s["last_upload"].isoformat() if s["last_upload"] else None,
                    "active": s["active"],
                }
                for token, s in self._sessions.items()
                if s["user"] == user
            ]

    def qr_bytes(self, token: str) -> Optional[bytes]:
        """Generate QR code for pairing token."""
        if not _QR:
            return None
        import io
        import os
        frontend_url = os.getenv("FRONTEND_URL", f"http://{settings.FASTAPI_HOST}:{settings.FASTAPI_PORT}")
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

    def pair_mobile(self, user: str, device_name: str = "Mobile Device") -> Dict[str, Any]:
        """Create pairing session and return token + QR code."""
        token = self.pairing.create_session(user, device_name)
        qr_b64 = self.pairing.qr_base64(token)
        return {
            "token": token,
            "qr_available": qr_b64 is not None,
            "qr_code": qr_b64,
            "expires_in_hours": 24,
            "server_url": f"http://{settings.FASTAPI_HOST}:{settings.FASTAPI_PORT}",
        }

    def validate_mobile(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate pairing token (includes session metadata)."""
        return self.pairing.validate(token)

    def record_mobile_upload(self, token: str) -> bool:
        """Record successful upload from paired device."""
        return self.pairing.record_upload(token)

    def revoke_mobile_session(self, token: str) -> bool:
        """Revoke a pairing session."""
        return self.pairing.revoke(token)

    def list_mobile_sessions(self, user: str) -> List[Dict[str, Any]]:
        """List all pairing sessions for a user."""
        return self.pairing.list_sessions(user)
