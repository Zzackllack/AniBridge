from __future__ import annotations
import sys
import os
from typing import Optional, Literal, Generator, Any
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from pathlib import Path
from loguru import logger

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logger.remove()
logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

from sqlmodel import SQLModel, Field, Session, create_engine, select, Column, JSON

from app.config import AVAILABILITY_TTL_HOURS

JobStatus = Literal["queued", "downloading", "completed", "failed", "cancelled"]

# ---- Datetime Helpers --------------------------------------------------------

def utcnow() -> datetime:
    # immer aware (UTC)
    return datetime.now(timezone.utc)

def as_aware_utc(dt: Optional[datetime]) -> datetime:
    """
    Normalisiert beliebige Datetimes zu aware/UTC.
    - None -> utcnow()
    - naive -> TZ auf UTC setzen (ohne Konvertierung, da naive!)
    - aware -> nach UTC konvertieren
    """
    if dt is None:
        return utcnow()
    if dt.tzinfo is None:
        # alte/naive Werte; wir interpretieren sie als UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

# ---------------- Jobs (wie gehabt) ------------------------------------------

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

# ---------------- Semi-Cache: Episode Availability ---------------------------

class EpisodeAvailability(SQLModel, table=True):
    """
    Semi-Cache: pro (slug, season, episode, language) speichern wir:
      - height/vcodec (aus Preflight-Probe)
      - available (bool): Sprache wirklich verfügbar?
      - provider (optional): welcher Provider hat funktioniert
      - checked_at: wann zuletzt geprüft
    """
    slug: str = Field(primary_key=True)
    season: int = Field(primary_key=True)
    episode: int = Field(primary_key=True)
    language: str = Field(primary_key=True)

    available: bool = True
    height: Optional[int] = None
    vcodec: Optional[str] = None
    provider: Optional[str] = None

    checked_at: datetime = Field(default_factory=utcnow, index=True)

    # Optional: zusätzliche Rohinfos (z. B. formats), falls du debug willst
    extra: Optional[dict] = Field(sa_column=Column(JSON), default=None)

    @property
    def is_fresh(self) -> bool:
        if AVAILABILITY_TTL_HOURS <= 0:
            return True
        # robust gegen naive Datetimes
        age = as_aware_utc(utcnow()) - as_aware_utc(self.checked_at)
        return age <= timedelta(hours=AVAILABILITY_TTL_HOURS)

# --- DB Bootstrap -------------------------------------------------------------

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

# --- Availability CRUD --------------------------------------------------------

def upsert_availability(
    session: Session,
    *,
    slug: str,
    season: int,
    episode: int,
    language: str,
    available: bool,
    height: Optional[int],
    vcodec: Optional[str],
    provider: Optional[str],
    extra: Optional[dict] = None,
) -> EpisodeAvailability:
    rec = session.get(EpisodeAvailability, (slug, season, episode, language))
    if rec is None:
        rec = EpisodeAvailability(
            slug=slug, season=season, episode=episode, language=language,
            available=available, height=height, vcodec=vcodec, provider=provider,
            extra=extra, checked_at=utcnow()
        )
        session.add(rec)
    else:
        rec.available = available
        rec.height = height
        rec.vcodec = vcodec
        rec.provider = provider
        rec.extra = extra
        rec.checked_at = utcnow()
        session.add(rec)
    session.commit()
    session.refresh(rec)
    return rec

def get_availability(
    session: Session, *, slug: str, season: int, episode: int, language: str
) -> Optional[EpisodeAvailability]:
    return session.get(EpisodeAvailability, (slug, season, episode, language))

def list_available_languages_cached(
    session: Session, *, slug: str, season: int, episode: int
) -> list[str]:
    rows = session.exec(
        select(EpisodeAvailability).where(
            (EpisodeAvailability.slug == slug) &
            (EpisodeAvailability.season == season) &
            (EpisodeAvailability.episode == episode) &
            (EpisodeAvailability.available == True)
        )
    ).all()
    # Nur frische Einträge zählen (mit robuster TZ-Behandlung)
    fresh_langs: list[str] = []
    for r in rows:
        try:
            if r.is_fresh:
                fresh_langs.append(r.language)
        except Exception as e:
            # falls ein Alt-Datensatz Probleme macht: konservativ ignorieren
            logger.warning(f"Skipping stale/invalid availability row for {r.slug} S{r.season}E{r.episode} {r.language}: {e}")
    return fresh_langs