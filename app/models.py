# app/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Literal
from uuid import uuid4
from pathlib import Path
from threading import Lock
import time

JobStatus = Literal["queued", "downloading", "completed", "failed"]

@dataclass
class Job:
    id: str
    status: JobStatus = "queued"
    progress: float = 0.0  # 0..100
    downloaded_bytes: int = 0
    total_bytes: Optional[int] = None
    speed: Optional[float] = None  # bytes/sec
    eta: Optional[int] = None      # seconds
    message: Optional[str] = None
    result_path: Optional[Path] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

class JobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = Lock()

    def create(self) -> Job:
        jid = uuid4().hex
        job = Job(id=jid)
        with self._lock:
            self._jobs[jid] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **fields) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for k, v in fields.items():
                setattr(job, k, v)
            job.updated_at = time.time()
            return job

store = JobStore()
