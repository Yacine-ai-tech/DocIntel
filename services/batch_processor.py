"""
BatchProcessor — job tracking for batch document processing, persisted durably.

Processes files concurrently with a bounded semaphore so a single job can fan out over
hundreds/thousands of documents without exhausting memory or hammering the LLM provider.
Each file is isolated: one failure never aborts the batch.

Job state is kept in memory for fast access but persisted on every state change, and
reloaded on startup. Previously state lived only in the in-memory `_jobs` dict: a
process restart (deploy, crash, OOM, a host recycling the instance) silently dropped
every in-flight/completed job — a client polling GET /batch/{job_id} afterward got
"unknown job" with no indication it ever ran. Completed jobs also never left memory at
all, growing unbounded for the process's lifetime (jobs retain every file's full
extracted results, not just metadata). Both are fixed here: persistence for durability
across restarts, and BATCH_JOB_TTL_SECONDS-based eviction (checked lazily on every
new_job() call, not a dedicated background loop) so the in-memory dict and the backing
store both stay bounded.

Persistence backend: Postgres (core.db) when POSTGRES_URL is set — durable across
restarts/redeploys and correct if this app ever runs as more than one instance, which a
local file never was. Falls back to LOGS_DIR/batch_jobs/*.json when unset, so a
single-container self-hoster needs zero database configuration.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core import db
from core.config import settings
from core.logger import get_logger

log = get_logger(__name__)

# Default fan-out width. Tune via BATCH_MAX_CONCURRENCY (LLM rate limits / CPU bound).
DEFAULT_CONCURRENCY = int(os.getenv("BATCH_MAX_CONCURRENCY", "8"))

# How long a job's state (and its results) stays retrievable after it last changed.
# Default 24h — long enough for a slow-to-poll client, short enough that this doesn't
# become its own unbounded-growth problem.
JOB_TTL_SECONDS = int(os.getenv("BATCH_JOB_TTL_SECONDS", str(24 * 3600)))

_STATE_DIR = Path(settings.LOGS_DIR) / "batch_jobs"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts(value) -> float:
    """Parse one of our own _now()-produced ISO timestamps back to epoch seconds.
    The DB backend round-trips these as native datetime objects (psycopg maps
    TIMESTAMPTZ directly), not strings, so accept either. Best-effort: an
    unparseable/missing timestamp is treated as "just happened" (0 age) rather
    than raising, so a corrupt field can't crash eviction."""
    if not value:
        return time.time()
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        return datetime.fromisoformat(value).timestamp()
    except (ValueError, TypeError):
        return time.time()


class BatchProcessor:
    """Batch processor with status tracking, bounded concurrency, disk persistence,
    and TTL-based eviction."""

    def __init__(self, max_concurrency: int = DEFAULT_CONCURRENCY):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self.max_concurrency = max(1, max_concurrency)
        if db.DB_ENABLED:
            try:
                db.ensure_schema()
            except Exception as e:
                # A Postgres connectivity hiccup at import time must not take down
                # the whole app — this constructor runs at module import (`batch =
                # BatchProcessor(...)` in api.py), so an unhandled exception here
                # crashed every request, not just batch processing. Falls back to
                # the same disk-persistence path used when POSTGRES_URL isn't set
                # at all, consistent with core.db's own "optional" contract.
                log.error("Postgres unavailable at startup (%s) — falling back to disk persistence for batch jobs", e)
                _STATE_DIR.mkdir(parents=True, exist_ok=True)
        else:
            _STATE_DIR.mkdir(parents=True, exist_ok=True)
        self._load_persisted_jobs()

    def _job_path(self, job_id: str) -> Path:
        return _STATE_DIR / f"{job_id}.json"

    def _persist(self, job_id: str, result_idx: Optional[int] = None) -> None:
        """Best-effort: a persistence failure must never break the actual batch
        processing it's trying to make durable. result_idx, when given, also
        persists just that one result row (DB backend only — the file backend
        always rewrites the whole job as one JSON blob either way)."""
        job = self._jobs.get(job_id)
        if job is None:
            return
        try:
            if db.DB_ENABLED:
                db.upsert_batch_job({
                    "id": job_id, "status": job["status"], "total": job["total"],
                    "processed": job["processed"], "failed": job["failed"],
                    "webhook_url": job.get("webhook_url"),
                    "created_at": job["created_at"], "updated_at": job["updated_at"],
                    "started_at": job.get("started_at"), "finished_at": job.get("finished_at"),
                })
                if result_idx is not None:
                    db.upsert_batch_result(job_id, result_idx, job["results"][result_idx])
            else:
                self._job_path(job_id).write_text(json.dumps(job))
        except Exception as e:
            log.warning("failed to persist job %s: %s", job_id, e)

    def _load_persisted_jobs(self) -> None:
        """Recover job state written before a restart. A job that was "running"
        when the process died can never actually resume (the in-process asyncio
        work is gone) — mark it failed rather than leaving it stuck at "running"
        forever, which would look like it's still in progress."""
        jobs: Dict[str, Dict[str, Any]] = {}
        if db.DB_ENABLED:
            try:
                jobs = db.load_all_batch_jobs()
            except Exception as e:
                log.warning("failed to load persisted jobs from Postgres: %s", e)
        else:
            if not _STATE_DIR.exists():
                return
            for f in _STATE_DIR.glob("*.json"):
                try:
                    job = json.loads(f.read_text())
                except Exception as e:
                    log.warning("failed to load persisted job from %s: %s", f, e)
                    continue
                job_id = job.get("id")
                if job_id:
                    jobs[job_id] = job

        for job_id, job in jobs.items():
            if job.get("status") == "running":
                job["status"] = "failed"
                job["error"] = "process restarted mid-job"
                job["updated_at"] = _now()
            self._jobs[job_id] = job
        self._evict_expired()

    def _evict_expired(self) -> None:
        cutoff = time.time() - JOB_TTL_SECONDS
        expired = [
            jid for jid, job in self._jobs.items()
            if _ts(job.get("finished_at") or job.get("updated_at") or job.get("created_at")) < cutoff
        ]
        for jid in expired:
            self._jobs.pop(jid, None)
            try:
                if db.DB_ENABLED:
                    db.delete_batch_job(jid)
                else:
                    self._job_path(jid).unlink(missing_ok=True)
            except Exception as e:
                log.warning("failed to evict persisted job %s: %s", jid, e)

    def new_job(self, total: int) -> str:
        """Create a new job and return its ID."""
        self._evict_expired()
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = {
            "id": job_id,
            "status": "pending",
            "total": total,
            "processed": 0,
            "failed": 0,
            "results": [None] * total,  # index-aligned for stable ordering
            "created_at": _now(),
            "updated_at": _now(),
        }
        self._persist(job_id)
        return job_id

    async def process(
        self,
        job_id: str,
        files: List[Dict[str, Any]],
        processor_fn: Callable,
        webhook_url: Optional[str] = None,
    ) -> None:
        """
        Process a batch concurrently in the background.

        Args:
            job_id: Pre-allocated job ID from new_job().
            files: List of {filename, bytes, doc_type, route} dicts.
            processor_fn: An async callable that processes one file and returns a dict.
            webhook_url: If set, POSTed with {job_id, status, total, processed, failed,
                results} once the job completes — used to trigger downstream automation
                (e.g. an n8n Webhook node; see docs/n8n/README.md) without polling.
        """
        job = self._jobs.get(job_id)
        if job is None:
            log.error("Unknown job_id: %s", job_id)
            return

        job["status"] = "running"
        job["started_at"] = _now()
        job["webhook_url"] = webhook_url
        self._persist(job_id)
        sem = asyncio.Semaphore(self.max_concurrency)

        async def _run(idx: int, file_data: Dict[str, Any]) -> None:
            async with sem:
                try:
                    job["results"][idx] = await processor_fn(file_data)
                    job["processed"] += 1
                except Exception as e:  # isolate per-file failures
                    log.exception("Batch item failed (%s): %s", file_data.get("filename"), e)
                    job["results"][idx] = {"error": str(e), "filename": file_data.get("filename")}
                    job["failed"] += 1
                job["updated_at"] = _now()
                # Persist incrementally (not just on final completion) so a restart
                # mid-batch still recovers whichever files had already finished,
                # instead of losing the entire job's progress.
                self._persist(job_id, result_idx=idx)

        await asyncio.gather(*(_run(i, fd) for i, fd in enumerate(files)))
        job["status"] = "completed"
        job["finished_at"] = _now()
        self._persist(job_id)

        if webhook_url:
            from services.webhook import send_webhook
            await send_webhook(webhook_url, {
                "job_id": job_id,
                "status": job["status"],
                "total": job["total"],
                "processed": job["processed"],
                "failed": job["failed"],
                "finished_at": job["finished_at"],
                "results": job["results"],
            })

    def get_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Return the job status (no results)."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        total = max(job["total"], 1)
        return {
            "id": job_id,
            "status": job["status"],
            "total": job["total"],
            "processed": job["processed"],
            "failed": job["failed"],
            "percent": round(100 * (job["processed"] + job["failed"]) / total, 1),
            "created_at": job["created_at"],
            "updated_at": job["updated_at"],
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
        }

    def get_results(self, job_id: str) -> Optional[List[Dict[str, Any]]]:
        """Return the list of per-file results (None entries = not yet processed)."""
        job = self._jobs.get(job_id)
        return job["results"] if job else None
