from __future__ import annotations
from typing import Optional, Literal, Generator, Any
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path

from sqlmodel import SQLModel, Field, Session, create_engine, select

JobStatus = Literal["queued", "downloading", "completed", "failed"]

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class Job(SQLModel, table=True):
    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True, index=True)
    status: str = Field(default="queued", index=True)
    progress: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: Optional[int] = None
    speed: Optional[float] = None
    eta: Optional[int] = None
    message: Optional[str] = None
    result_path: Optional[str] = None

    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)

# --- DB Bootstrap ---
# SQLite-Datei unter ./data; stelle sicher, dass ./data existiert
DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{(DATA_DIR / 'anibridge_jobs.db').as_posix()}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

# --- CRUD / Helpers ---
def create_job(session: Session) -> Job:
    job = Job()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job

def get_job(session: Session, job_id: str) -> Optional[Job]:
    return session.get(Job, job_id)

def update_job(session: Session, job_id: str, **fields: Any) -> Optional[Job]:
    job = session.get(Job, job_id)
    if not job:
        return None
    for k, v in fields.items():
        setattr(job, k, v)
    job.updated_at = utcnow()
    session.add(job)
    session.commit()
    session.refresh(job)
    return job

def cleanup_dangling_jobs(session: Session) -> int:
    """
    Setzt Jobs, die beim Start in queued/downloading hängen, auf failed.
    """
    rows = session.exec(select(Job).where(Job.status.in_(["queued", "downloading"]))).all() # type: ignore
    for j in rows:
        j.status = "failed"
        j.message = "Interrupted by application restart"
        j.updated_at = utcnow()
        session.add(j)
    session.commit()
    return len(rows)