from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Event, Lock
from typing import Callable, Any
from uuid import uuid4

from .cancellation import OperationCancelledError


JobFunc = Callable[[Callable[[], bool]], Any]


@dataclass
class JobRecord:
    job_id: str
    status: str
    created_at: str
    updated_at: str
    cancel_event: Event = field(default_factory=Event)
    future: Future | None = None
    result: Any = None
    error: str | None = None


class JobManager:
    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_job(self, func: JobFunc) -> JobRecord:
        job_id = str(uuid4())
        now = self._now_iso()
        record = JobRecord(
            job_id=job_id,
            status="queued",
            created_at=now,
            updated_at=now,
        )

        def _runner() -> Any:
            with self._lock:
                if record.cancel_event.is_set():
                    record.status = "cancelled"
                    record.updated_at = self._now_iso()
                    return None
                record.status = "running"
                record.updated_at = self._now_iso()

            try:
                output = func(record.cancel_event.is_set)
                with self._lock:
                    if record.cancel_event.is_set():
                        record.status = "cancelled"
                        record.result = None
                    else:
                        record.status = "completed"
                        record.result = output
                    record.updated_at = self._now_iso()
                return output
            except OperationCancelledError:
                with self._lock:
                    record.status = "cancelled"
                    record.result = None
                    record.updated_at = self._now_iso()
                return None
            except Exception as exc:
                with self._lock:
                    record.status = "failed"
                    record.error = str(exc)
                    record.updated_at = self._now_iso()
                return None

        with self._lock:
            self._jobs[job_id] = record
            record.future = self._executor.submit(_runner)
            return record

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> JobRecord | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return None
            record.cancel_event.set()
            if record.status in {"queued", "running"}:
                record.status = "cancelling"
                record.updated_at = self._now_iso()
            return record

