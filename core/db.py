"""
Optional Postgres persistence — batch jobs and camera-pairing sessions.

Only active when POSTGRES_URL is set (see core/config.py). Uses psycopg 3
directly (no ORM) since the access patterns here are simple key-value/record
lookups, not relational queries. Tables are created idempotently on first use
(CREATE TABLE IF NOT EXISTS) — no separate migration step.

psycopg is an optional dependency: importing this module when POSTGRES_URL is
unset never touches psycopg at all, so a self-hoster without Postgres doesn't
need it installed.
"""
from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

from core.config import settings
from core.logger import get_logger

log = get_logger(__name__)

DB_ENABLED = bool(settings.POSTGRES_URL)

_pool = None
_pool_lock = threading.Lock()
_schema_ready = False


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            from psycopg_pool import ConnectionPool
            _pool = ConnectionPool(settings.POSTGRES_URL, min_size=1, max_size=5, open=True)
    return _pool


@contextmanager
def get_conn() -> Iterator[Any]:
    """Yield a psycopg connection from the pool. Only call when DB_ENABLED is True."""
    pool = _get_pool()
    with pool.connection() as conn:
        yield conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS batch_jobs (
    id           TEXT PRIMARY KEY,
    status       TEXT NOT NULL,
    total        INTEGER NOT NULL,
    processed    INTEGER NOT NULL DEFAULT 0,
    failed       INTEGER NOT NULL DEFAULT 0,
    webhook_url  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ,
    owner_session_id TEXT
);

CREATE TABLE IF NOT EXISTS batch_results (
    job_id       TEXT NOT NULL REFERENCES batch_jobs(id) ON DELETE CASCADE,
    idx          INTEGER NOT NULL,
    result       JSONB,
    PRIMARY KEY (job_id, idx)
);

CREATE TABLE IF NOT EXISTS camera_sessions (
    token         TEXT PRIMARY KEY,
    app_user      TEXT NOT NULL,
    device_name   TEXT,
    created_at    TIMESTAMPTZ NOT NULL,
    expires_at    TIMESTAMPTZ NOT NULL,
    uploads       INTEGER NOT NULL DEFAULT 0,
    last_upload   TIMESTAMPTZ,
    last_result   JSONB,
    active        BOOLEAN NOT NULL DEFAULT TRUE
);
"""


def ensure_schema() -> None:
    """Idempotent CREATE TABLE IF NOT EXISTS — safe to call on every startup."""
    global _schema_ready
    if _schema_ready or not DB_ENABLED:
        return
    with get_conn() as conn:
        conn.execute(_SCHEMA)
        # Idempotent migration for tables created before owner_session_id existed.
        conn.execute("ALTER TABLE batch_jobs ADD COLUMN IF NOT EXISTS owner_session_id TEXT")
        conn.commit()
    _schema_ready = True
    log.info("Postgres schema ready (batch_jobs, batch_results, camera_sessions)")


def _row_to_dict(cur) -> list:
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# ─── Batch jobs ───────────────────────────────────────────────────────────────

def upsert_batch_job(job: Dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO batch_jobs (id, status, total, processed, failed, webhook_url,
                                     created_at, updated_at, started_at, finished_at,
                                     owner_session_id)
            VALUES (%(id)s, %(status)s, %(total)s, %(processed)s, %(failed)s, %(webhook_url)s,
                    %(created_at)s, %(updated_at)s, %(started_at)s, %(finished_at)s,
                    %(owner_session_id)s)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                processed = EXCLUDED.processed,
                failed = EXCLUDED.failed,
                updated_at = EXCLUDED.updated_at,
                started_at = EXCLUDED.started_at,
                finished_at = EXCLUDED.finished_at
            """,
            {**job, "owner_session_id": job.get("owner_session_id")},
        )
        conn.commit()


def upsert_batch_result(job_id: str, idx: int, result: Optional[Dict[str, Any]]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO batch_results (job_id, idx, result)
            VALUES (%s, %s, %s)
            ON CONFLICT (job_id, idx) DO UPDATE SET result = EXCLUDED.result
            """,
            (job_id, idx, json.dumps(result) if result is not None else None),
        )
        conn.commit()


def load_all_batch_jobs() -> Dict[str, Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM batch_jobs")
        jobs = {r["id"]: r for r in _row_to_dict(cur)}
        for job in jobs.values():
            job["results"] = [None] * job["total"]
        cur = conn.execute("SELECT job_id, idx, result FROM batch_results ORDER BY job_id, idx")
        for r in _row_to_dict(cur):
            job = jobs.get(r["job_id"])
            if job is None or r["idx"] >= len(job["results"]):
                continue
            job["results"][r["idx"]] = r["result"]
    return jobs


def delete_batch_job(job_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM batch_jobs WHERE id = %s", (job_id,))
        conn.commit()


# ─── Camera sessions ──────────────────────────────────────────────────────────

def upsert_camera_session(token: str, session: Dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO camera_sessions (token, app_user, device_name, created_at, expires_at,
                                          uploads, last_upload, last_result, active)
            VALUES (%(token)s, %(user)s, %(device_name)s, %(created_at)s, %(expires_at)s,
                    %(uploads)s, %(last_upload)s, %(last_result)s, %(active)s)
            ON CONFLICT (token) DO UPDATE SET
                uploads = EXCLUDED.uploads, last_upload = EXCLUDED.last_upload,
                last_result = EXCLUDED.last_result, active = EXCLUDED.active
            """,
            {
                "token": token,
                "user": session.get("user"),
                "device_name": session.get("device_name"),
                "created_at": session.get("created_at"),
                "expires_at": session.get("expires_at"),
                "uploads": session.get("uploads", 0),
                "last_upload": session.get("last_upload"),
                "last_result": json.dumps(session["last_result"]) if session.get("last_result") is not None else None,
                "active": session.get("active", True),
            },
        )
        conn.commit()


def load_all_camera_sessions() -> Dict[str, Dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM camera_sessions")
        rows = _row_to_dict(cur)
    out = {}
    for r in rows:
        out[r["token"]] = {
            "user": r["app_user"],
            "device_name": r["device_name"],
            "created_at": r["created_at"],
            "expires_at": r["expires_at"],
            "uploads": r["uploads"],
            "last_upload": r["last_upload"],
            "last_result": r["last_result"],
            "active": r["active"],
        }
    return out


def delete_camera_session(token: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM camera_sessions WHERE token = %s", (token,))
        conn.commit()
