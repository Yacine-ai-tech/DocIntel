"""
BatchProcessor — In-memory job tracking for batch document processing.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from core.logger import get_logger

log = get_logger(__name__)


class BatchProcessor:
    """In-memory batch processor with status tracking."""

    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}

    def new_job(self, total: int) -> str:
        """Create a new job and return its ID."""
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = {
            "id": job_id,
            "status": "pending",
            "total": total,
            "processed": 0,
            "failed": 0,
            "results": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        return job_id

    async def process(
        self,
        job_id: str,
        files: List[Dict[str, Any]],
        processor_fn: Callable,
    ) -> None:
        """
        Process a batch in the background.

        Args:
            job_id: Pre-allocated job ID from new_job().
            files: List of {filename, bytes, doc_type} dicts.
            processor_fn: An async callable that processes one file and returns a dict.
        """
        if job_id not in self._jobs:
            log.error("Unknown job_id: %s", job_id)
            return

        self._jobs[job_id]["status"] = "running"
        for file_data in files:
            try:
                result = await processor_fn(file_data)
                self._jobs[job_id]["results"].append(result)
                self._jobs[job_id]["processed"] += 1
            except Exception as e:
                log.exception("Batch item failed: %s", e)
                self._jobs[job_id]["failed"] += 1
                self._jobs[job_id]["results"].append({"error": str(e), "file": file_data.get("filename")})
            self._jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
        self._jobs[job_id]["status"] = "completed"

    def get_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Return the job status (no results)."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        total = max(job["total"], 1)
        percent = round(100 * (job["processed"] + job["failed"]) / total, 1)
        return {
            "id": job_id,
            "status": job["status"],
            "total": job["total"],
            "processed": job["processed"],
            "failed": job["failed"],
            "percent": percent,
            "created_at": job["created_at"],
            "updated_at": job["updated_at"],
        }

    def get_results(self, job_id: str) -> Optional[List[Dict[str, Any]]]:
        """Return the list of per-file results."""
        job = self._jobs.get(job_id)
        return job["results"] if job else None
