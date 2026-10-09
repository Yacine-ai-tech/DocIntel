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


def _get_pooler_url(url: str) -> str:
    """Enforce Neon PgBouncer -pooler endpoint to eliminate TCP/TLS handshake latency."""
    if not url or "-pooler" in url or "neon.tech" not in url:
        return url
    import re
    return re.sub(r'(@ep-[a-z0-9-]+)(\.[a-z0-9-.]*neon\.tech)', r'\1-pooler\2', url)


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            from psycopg_pool import ConnectionPool
            pool_url = _get_pooler_url(settings.POSTGRES_URL)
            _pool = ConnectionPool(
                pool_url,
                min_size=2,
                max_size=10,
                max_idle=300,
                timeout=10.0,
                reconnect_timeout=30,
                reconnect_failed=None,
                check=ConnectionPool.check_connection,
                open=True,
            )
            log.info("✅ DocIntel Neon connection pool initialized (min=2, max=10, pooler enabled)")
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

CREATE TABLE IF NOT EXISTS docintel_documents (
    id                 TEXT PRIMARY KEY,
    filename           TEXT NOT NULL,
    file_size          INTEGER,
    mime_type          TEXT,
    doc_type           TEXT,
    route              TEXT,
    confidence         DOUBLE PRECISION,
    page_count         INTEGER,
    processing_time_ms DOUBLE PRECISION,
    fields             JSONB,
    tables             JSONB,
    raw_text           TEXT,
    markdown           TEXT,
    status             TEXT NOT NULL DEFAULT 'completed',
    error              TEXT,
    owner_session_id   TEXT,
    metadata           JSONB,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_docintel_docs_created_at ON docintel_documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_docintel_docs_doc_type ON docintel_documents(doc_type);
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
    log.info("Postgres schema ready (batch_jobs, batch_results, camera_sessions, docintel_documents)")


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


# ─── Processed Documents & Extractions ───────────────────────────────────────

def upsert_document(doc: Dict[str, Any]) -> str:
    """Persist or update an extracted document record with structured fields and metadata."""
    import uuid
    from datetime import datetime, timezone

    doc_id = doc.get("id") or f"doc_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    
    fields_json = json.dumps(doc["fields"]) if doc.get("fields") is not None else None
    tables_json = json.dumps(doc["tables"]) if doc.get("tables") is not None else None
    meta_json = json.dumps(doc["metadata"]) if doc.get("metadata") is not None else None

    params = {
        "id": doc_id,
        "filename": doc.get("filename") or "untitled",
        "file_size": doc.get("file_size"),
        "mime_type": doc.get("mime_type"),
        "doc_type": doc.get("doc_type"),
        "route": doc.get("route"),
        "confidence": doc.get("confidence"),
        "page_count": doc.get("page_count"),
        "processing_time_ms": doc.get("processing_time_ms"),
        "fields": fields_json,
        "tables": tables_json,
        "raw_text": doc.get("raw_text"),
        "markdown": doc.get("markdown"),
        "status": doc.get("status", "completed"),
        "error": doc.get("error"),
        "owner_session_id": doc.get("owner_session_id"),
        "metadata": meta_json,
        "created_at": doc.get("created_at") or now,
        "updated_at": now,
    }

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO docintel_documents (
                id, filename, file_size, mime_type, doc_type, route, confidence,
                page_count, processing_time_ms, fields, tables, raw_text, markdown,
                status, error, owner_session_id, metadata, created_at, updated_at
            ) VALUES (
                %(id)s, %(filename)s, %(file_size)s, %(mime_type)s, %(doc_type)s, %(route)s, %(confidence)s,
                %(page_count)s, %(processing_time_ms)s, %(fields)s, %(tables)s, %(raw_text)s, %(markdown)s,
                %(status)s, %(error)s, %(owner_session_id)s, %(metadata)s, %(created_at)s, %(updated_at)s
            )
            ON CONFLICT (id) DO UPDATE SET
                filename = EXCLUDED.filename,
                file_size = EXCLUDED.file_size,
                mime_type = EXCLUDED.mime_type,
                doc_type = EXCLUDED.doc_type,
                route = EXCLUDED.route,
                confidence = EXCLUDED.confidence,
                page_count = EXCLUDED.page_count,
                processing_time_ms = EXCLUDED.processing_time_ms,
                fields = EXCLUDED.fields,
                tables = EXCLUDED.tables,
                raw_text = EXCLUDED.raw_text,
                markdown = EXCLUDED.markdown,
                status = EXCLUDED.status,
                error = EXCLUDED.error,
                metadata = EXCLUDED.metadata,
                updated_at = EXCLUDED.updated_at
            """,
            params,
        )
        conn.commit()
    return doc_id


def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single document by its unique ID."""
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM docintel_documents WHERE id = %s", (doc_id,))
        rows = _row_to_dict(cur)
        if not rows:
            return None
        doc = rows[0]
        # Format datetimes to ISO string
        if doc.get("created_at"):
            doc["created_at"] = doc["created_at"].isoformat()
        if doc.get("updated_at"):
            doc["updated_at"] = doc["updated_at"].isoformat()
        return doc


def list_documents(
    limit: int = 50,
    offset: int = 0,
    doc_type: Optional[str] = None,
    route: Optional[str] = None,
    search: Optional[str] = None,
    owner_session_id: Optional[str] = None,
    is_admin: bool = False,
) -> List[Dict[str, Any]]:
    """List documents with optional filtering, pagination, and session scoping."""
    clauses: List[str] = []
    params: List[Any] = []

    if doc_type and doc_type != "all":
        clauses.append("doc_type = %s")
        params.append(doc_type)
    if route and route != "all":
        clauses.append("route = %s")
        params.append(route)
    if not is_admin and owner_session_id != "*":
        if owner_session_id:
            clauses.append("(owner_session_id = %s OR owner_session_id IS NULL)")
            params.append(owner_session_id)
        else:
            clauses.append("owner_session_id IS NULL")
    if search:
        clauses.append("(filename ILIKE %s OR doc_type ILIKE %s OR raw_text ILIKE %s)")
        term = f"%{search}%"
        params.extend([term, term, term])

    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT id, filename, file_size, mime_type, doc_type, route, confidence,
               page_count, processing_time_ms, fields, tables, raw_text, markdown,
               status, error, owner_session_id, metadata, created_at, updated_at
        FROM docintel_documents{where_sql}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    with get_conn() as conn:
        cur = conn.execute(sql, params)
        rows = _row_to_dict(cur)
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = r["created_at"].isoformat()
            if r.get("updated_at"):
                r["updated_at"] = r["updated_at"].isoformat()
        return rows


def count_documents(
    doc_type: Optional[str] = None,
    route: Optional[str] = None,
    search: Optional[str] = None,
    owner_session_id: Optional[str] = None,
    is_admin: bool = False,
) -> int:
    """Return total count of documents matching the filter criteria."""
    clauses: List[str] = []
    params: List[Any] = []

    if doc_type and doc_type != "all":
        clauses.append("doc_type = %s")
        params.append(doc_type)
    if route and route != "all":
        clauses.append("route = %s")
        params.append(route)
    if not is_admin and owner_session_id != "*":
        if owner_session_id:
            clauses.append("(owner_session_id = %s OR owner_session_id IS NULL)")
            params.append(owner_session_id)
        else:
            clauses.append("owner_session_id IS NULL")
    if search:
        clauses.append("(filename ILIKE %s OR doc_type ILIKE %s OR raw_text ILIKE %s)")
        term = f"%{search}%"
        params.extend([term, term, term])

    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT COUNT(*) AS total FROM docintel_documents{where_sql}"

    with get_conn() as conn:
        cur = conn.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else 0


def delete_document(doc_id: str) -> bool:
    """Delete a document record by ID."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM docintel_documents WHERE id = %s", (doc_id,))
        conn.commit()
        return cur.rowcount > 0


def clear_all_documents(owner_session_id: Optional[str] = None) -> int:
    """Delete all documents or documents belonging to a session."""
    with get_conn() as conn:
        if owner_session_id:
            cur = conn.execute("DELETE FROM docintel_documents WHERE owner_session_id = %s", (owner_session_id,))
        else:
            cur = conn.execute("DELETE FROM docintel_documents")
        conn.commit()
        return cur.rowcount


def get_documents_stats(owner_session_id: Optional[str] = None, is_admin: bool = False) -> Dict[str, Any]:
    """Compute aggregate statistical metrics across stored documents in Neon DB."""
    if is_admin or owner_session_id == "*":
        where_sql = ""
        params: List[Any] = []
    elif owner_session_id:
        where_sql = " WHERE (owner_session_id = %s OR owner_session_id IS NULL)"
        params = [owner_session_id]
    else:
        where_sql = " WHERE owner_session_id IS NULL"
        params = []

    with get_conn() as conn:
        # Aggregates
        cur = conn.execute(
            f"""
            SELECT
                COUNT(*) AS total_count,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) AS successful_count,
                COUNT(CASE WHEN status = 'error' THEN 1 END) AS error_count,
                COALESCE(AVG(confidence), 0.0) AS avg_confidence,
                COALESCE(AVG(processing_time_ms), 0.0) AS avg_processing_time_ms,
                COALESCE(SUM(page_count), 0) AS total_pages
            FROM docintel_documents{where_sql}
            """,
            params,
        )
        agg_row = _row_to_dict(cur)[0]

        # By doc_type
        cur = conn.execute(
            f"""
            SELECT COALESCE(doc_type, 'unclassified') AS doc_type, COUNT(*) AS count
            FROM docintel_documents{where_sql}
            GROUP BY doc_type
            ORDER BY count DESC
            """,
            params,
        )
        by_type = {r["doc_type"]: r["count"] for r in _row_to_dict(cur)}

        # By route
        cur = conn.execute(
            f"""
            SELECT COALESCE(route, 'unknown') AS route, COUNT(*) AS count
            FROM docintel_documents{where_sql}
            GROUP BY route
            ORDER BY count DESC
            """,
            params,
        )
        by_route = {r["route"]: r["count"] for r in _row_to_dict(cur)}

        # Recent timeline (last 7 days)
        cur = conn.execute(
            f"""
            SELECT to_char(created_at, 'YYYY-MM-DD') AS day, COUNT(*) AS count
            FROM docintel_documents{where_sql}
            GROUP BY day
            ORDER BY day DESC
            LIMIT 7
            """,
            params,
        )
        recent_timeline = _row_to_dict(cur)

    return {
        "total_documents": agg_row["total_count"],
        "successful_documents": agg_row["successful_count"],
        "error_documents": agg_row["error_count"],
        "avg_confidence": round(float(agg_row["avg_confidence"]), 4),
        "avg_processing_time_ms": round(float(agg_row["avg_processing_time_ms"]), 2),
        "total_pages": int(agg_row["total_pages"]),
        "by_doc_type": by_type,
        "by_route": by_route,
        "recent_timeline": recent_timeline,
    }

