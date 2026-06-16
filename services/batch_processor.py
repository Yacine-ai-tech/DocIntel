"""
BatchProcessor — in-memory job tracking for batch document processing.

Processes files concurrently with a bounded semaphore so a single job can fan out over
hundreds/thousands of documents without exhausting memory or hammering the LLM provider.
Each file is isolated: one failure never aborts the batch.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from core.logger import get_logger

log = get_logger(__name__)

# Default fan-out width. Tune via BATCH_MAX_CONCURRENCY (LLM rate limits / CPU bound).
DEFAULT_CONCURRENCY = int(os.getenv("BATCH_MAX_CONCURRENCY", "8"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BatchProcessor:
    """In-memory batch processor with status tracking and bounded concurrency."""

    def __init__(self, max_concurrency: int = DEFAULT_CONCURRENCY):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self.max_concurrency = max(1, max_concurrency)

    def new_job(self, total: int) -> str:
        """Create a new job and return its ID."""
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
        return job_id

    async def process(
        self,
        job_id: str,
        files: List[Dict[str, Any]],
        processor_fn: Callable,
    ) -> None:
        """
        Process a batch concurrently in the background.

        Args:
            job_id: Pre-allocated job ID from new_job().
            files: List of {filename, bytes, doc_type, route} dicts.
            processor_fn: An async callable that processes one file and returns a dict.
        """
        job = self._jobs.get(job_id)
        if job is None:
            log.error("Unknown job_id: %s", job_id)
            return

        job["status"] = "running"
        job["started_at"] = _now()
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

        await asyncio.gather(*(_run(i, fd) for i, fd in enumerate(files)))
        job["status"] = "completed"
        job["finished_at"] = _now()

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
