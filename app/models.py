from __future__ import annotations
import sys
import os
from typing import Optional, Literal, Generator, Any
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from loguru import logger
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logger.remove()
logger.add(sys.stdout, level=LOG_LEVEL, colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

from sqlmodel import SQLModel, Field, Session, create_engine, select

JobStatus = Literal["queued", "downloading", "completed", "failed"]

def utcnow() -> datetime:
    now = datetime.now(timezone.utc)
    logger.debug(f"utcnow() called, returning {now}")
    return now

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
logger.debug(f"DATA_DIR for jobs DB: {DATA_DIR}")
DATABASE_URL = f"sqlite:///{(DATA_DIR / 'anibridge_jobs.db').as_posix()}"
logger.debug(f"DATABASE_URL: {DATABASE_URL}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
logger.debug("SQLModel engine created.")

def create_db_and_tables() -> None:
    logger.debug("Creating DB and tables if not exist.")
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    logger.debug("Creating new DB session.")
    with Session(engine) as session:
        yield session

# --- CRUD / Helpers ---
def create_job(session: Session) -> Job:
    logger.debug("Creating new job entry in DB.")
    job = Job()
    session.add(job)
    session.commit()
    session.refresh(job)
    logger.success(f"Created job {job.id}")
    return job

def get_job(session: Session, job_id: str) -> Optional[Job]:
    logger.debug(f"Fetching job {job_id} from DB.")
    return session.get(Job, job_id)

def update_job(session: Session, job_id: str, **fields: Any) -> Optional[Job]:
    logger.debug(f"Updating job {job_id} with fields {fields}")
    job = session.get(Job, job_id)
    if not job:
        logger.warning(f"Job {job_id} not found for update.")
        return None
    for k, v in fields.items():
        setattr(job, k, v)
    job.updated_at = utcnow()
    session.add(job)
    session.commit()
    session.refresh(job)
    logger.success(f"Updated job {job_id}")
    return job

def cleanup_dangling_jobs(session: Session) -> int:
    logger.debug("Cleaning up dangling jobs (queued/downloading) on startup.")
    rows = session.exec(select(Job).where(Job.status.in_(["queued", "downloading"]))).all() # type: ignore
    for j in rows:
        j.status = "failed"
        j.message = "Interrupted by application restart"
        j.updated_at = utcnow()
        session.add(j)
    session.commit()
    logger.debug(f"Set {len(rows)} jobs to failed.")
    return len(rows)