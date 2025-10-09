from __future__ import annotations
import sys
import os
from typing import Optional, Literal, Generator, Any, List
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from loguru import logger

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logger.remove()
logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)

from sqlmodel import SQLModel, Field, Session, create_engine, select, Column, JSON
from sqlalchemy import UniqueConstraint
from sqlalchemy import inspect, text
from sqlalchemy.orm import registry as sa_registry
from sqlalchemy.pool import NullPool

from app.config import AVAILABILITY_TTL_HOURS, DATA_DIR

JobStatus = Literal["queued", "downloading", "completed", "failed", "cancelled"]


# ---- Datetime Helpers
def utcnow() -> datetime:
    logger.debug("utcnow() called.")
    return datetime.now(timezone.utc)


def as_aware_utc(dt: Optional[datetime]) -> datetime:
    logger.debug(f"as_aware_utc() called with dt={dt}")
    if dt is None:
        logger.info("Datetime is None, returning utcnow().")
        return utcnow()
    if dt.tzinfo is None:
        logger.info("Datetime is naive, setting tzinfo to UTC.")
        return dt.replace(tzinfo=timezone.utc)
    logger.info("Datetime is aware, converting to UTC.")
    return dt.astimezone(timezone.utc)


# ---------------- Jobs
# Use a private registry/base to avoid SQLModel's global default registry
# being reused across test re-imports (which causes SAWarnings about
# duplicate class names). Each import of this module creates a fresh
# registry and metadata.
_registry = sa_registry()


class ModelBase(SQLModel, registry=_registry):  # type: ignore[call-arg]
    pass


class Job(ModelBase, table=True):
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


# ---------------- Semi-Cache: Episode Availability
class EpisodeAvailability(ModelBase, table=True):
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
    extra: Optional[dict] = Field(sa_column=Column(JSON), default=None)

    @property
    def is_fresh(self) -> bool:
        logger.debug(
            f"Checking freshness for {self.slug} S{self.season}E{self.episode} {self.language}"
        )
        if AVAILABILITY_TTL_HOURS <= 0:
            logger.info("AVAILABILITY_TTL_HOURS <= 0, always fresh.")
            return True
        age = as_aware_utc(utcnow()) - as_aware_utc(self.checked_at)
        logger.debug(f"Age of availability: {age}")
        return age <= timedelta(hours=AVAILABILITY_TTL_HOURS)


# ---------------- Absolute Episode Mapping
class EpisodeNumberMapping(ModelBase, table=True):
    __table_args__ = (
        UniqueConstraint("series_slug", "absolute_number"),
        UniqueConstraint("series_slug", "season_number", "episode_number"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    series_slug: str = Field(index=True)
    absolute_number: int
    season_number: int
    episode_number: int
    episode_title: Optional[str] = None
    last_synced_at: datetime = Field(default_factory=utcnow, index=True)


# ---------------- qBittorrent-Shim: ClientTask
class ClientTask(ModelBase, table=True):
    """
    Abbildung eines „Torrents“ (Magnet) auf unseren internen Job.
    """

    hash: str = Field(primary_key=True, index=True)  # entspricht btih (aus magnet xt)
    name: str
    slug: str
    season: int
    episode: int
    absolute_number: Optional[int] = Field(default=None, index=True)
    language: str
    job_id: Optional[str] = Field(default=None, index=True)
    save_path: Optional[str] = None
    category: Optional[str] = None
    added_on: datetime = Field(default_factory=utcnow, index=True)
    completion_on: Optional[datetime] = None
    state: str = Field(
        default="queued", index=True
    )  # queued/downloading/paused/completed/error


# ---------------- Engine and Session utilities
DATABASE_URL = f"sqlite:///{(DATA_DIR / 'anibridge_jobs.db').as_posix()}"
logger.debug(f"DATABASE_URL: {DATABASE_URL}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=NullPool,  # ensure connections are closed when sessions end
)
logger.debug("SQLModel engine created.")


def create_db_and_tables() -> None:
    logger.debug("Creating DB and tables if not exist.")
    try:
        # Use this module's private metadata
        ModelBase.metadata.create_all(engine)
        logger.success("Database and tables created or already exist.")
        table_names = sorted(ModelBase.metadata.tables.keys())
        logger.debug("Available tables after creation: {}", table_names)
        try:
            insp = inspect(engine)
            columns = {col["name"] for col in insp.get_columns("clienttask")}
            if "absolute_number" not in columns:
                logger.info(
                    "Adding missing 'absolute_number' column to clienttask table."
                )
                with engine.begin() as conn:
                    conn.execute(
                        text("ALTER TABLE clienttask ADD COLUMN absolute_number INTEGER")
                    )
        except Exception as mig_exc:
            logger.error(
                "Failed to verify or add clienttask.absolute_number column: {}", mig_exc
            )
    except Exception as e:
        logger.error(f"Error creating DB and tables: {e}")


def get_session() -> Generator[Session, None, None]:
    logger.debug("Creating new DB session.")
    try:
        with Session(engine) as session:
            logger.debug("DB session created.")
            yield session
    except Exception as e:
        logger.error(f"Error creating DB session: {e}")
        raise


def dispose_engine() -> None:
    """Dispose the global SQLAlchemy engine to close any pooled connections.

    This helps tests and short-lived runs avoid ResourceWarning: unclosed database.
    """
    try:
        engine.dispose()
        logger.debug("SQLAlchemy engine disposed.")
    except Exception as e:
        logger.warning(f"Engine dispose error: {e}")


# --- Jobs CRUD
def create_job(session: Session) -> Job:
    logger.debug("Creating new job entry in DB.")
    try:
        job = Job()
        session.add(job)
        session.commit()
        session.refresh(job)
        logger.success(f"Created job {job.id}")
        return job
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise


def get_job(session: Session, job_id: str) -> Optional[Job]:
    logger.debug(f"Fetching job {job_id} from DB.")
    job = session.get(Job, job_id)
    if job:
        logger.debug(f"Job {job_id} found.")
    else:
        logger.warning(f"Job {job_id} not found.")
    return job


def update_job(session: Session, job_id: str, **fields: Any) -> Optional[Job]:
    logger.debug(f"Updating job {job_id} with fields {fields}")
    job = session.get(Job, job_id)
    if not job:
        logger.warning(f"Job {job_id} not found for update.")
        return None
    for k, v in fields.items():
        logger.debug(f"Setting {k} to {v} for job {job_id}")
        setattr(job, k, v)
    job.updated_at = utcnow()
    session.add(job)
    try:
        session.commit()
        session.refresh(job)
        # Avoid console spam on frequent progress updates
        logger.debug(f"Updated job {job_id}")
    except Exception as e:
        logger.error(f"Failed to update job {job_id}: {e}")
        raise
    return job


def cleanup_dangling_jobs(session: Session) -> int:
    logger.debug("Cleaning up dangling jobs (queued/downloading) on startup.")
    rows = session.exec(select(Job).where(Job.status.in_(["queued", "downloading"]))).all()  # type: ignore
    if not rows:
        logger.info("No dangling jobs found to clean up.")
    for j in rows:
        logger.info(f"Marking job {j.id} as failed due to restart.")
        j.status = "failed"
        j.message = "Interrupted by application restart"
        j.updated_at = utcnow()
        session.add(j)
    session.commit()
    logger.debug(f"Set {len(rows)} jobs to failed.")
    return len(rows)


# --- Availability CRUD
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
    logger.debug(f"Upserting availability for {slug} S{season}E{episode} {language}")
    rec = session.get(EpisodeAvailability, (slug, season, episode, language))
    if rec is None:
        logger.info("No existing availability record found, creating new.")
        rec = EpisodeAvailability(
            slug=slug,
            season=season,
            episode=episode,
            language=language,
            available=available,
            height=height,
            vcodec=vcodec,
            provider=provider,
            extra=extra,
            checked_at=utcnow(),
        )
        session.add(rec)
    else:
        logger.info("Existing availability record found, updating.")
        rec.available = available
        rec.height = height
        rec.vcodec = vcodec
        rec.provider = provider
        rec.extra = extra
        rec.checked_at = utcnow()
        session.add(rec)
    try:
        session.commit()
        session.refresh(rec)
        logger.success(
            f"Upserted availability for {slug} S{season}E{episode} {language}"
        )
    except Exception as e:
        logger.error(f"Failed to upsert availability: {e}")
        raise
    return rec


def get_availability(
    session: Session, *, slug: str, season: int, episode: int, language: str
) -> Optional[EpisodeAvailability]:
    logger.debug(f"Fetching availability for {slug} S{season}E{episode} {language}")
    rec = session.get(EpisodeAvailability, (slug, season, episode, language))
    if rec:
        logger.debug("Availability record found.")
    else:
        logger.warning("Availability record not found.")
    return rec


def list_available_languages_cached(
    session: Session, *, slug: str, season: int, episode: int
) -> List[str]:
    logger.debug(f"Listing available cached languages for {slug} S{season}E{episode}")
    rows = session.exec(
        select(EpisodeAvailability).where(
            (EpisodeAvailability.slug == slug)
            & (EpisodeAvailability.season == season)
            & (EpisodeAvailability.episode == episode)
            & (EpisodeAvailability.available == True)
        )
    ).all()
    fresh_langs: List[str] = []
    for r in rows:
        try:
            if r.is_fresh:
                logger.debug(f"Language {r.language} is fresh and available.")
                fresh_langs.append(r.language)
            else:
                logger.info(f"Language {r.language} is stale.")
        except Exception as e:
            logger.warning(
                f"Skipping stale/invalid availability row for {r.slug} S{r.season}E{r.episode} {r.language}: {e}"
            )
    logger.info(f"Available fresh languages: {fresh_langs}")
    return fresh_langs


# --- Episode Mapping CRUD
def _ensure_positive(value: int, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")


def upsert_episode_mapping(
    session: Session,
    *,
    series_slug: str,
    absolute_number: int,
    season_number: int,
    episode_number: int,
    episode_title: Optional[str] = None,
    last_synced_at: Optional[datetime] = None,
) -> EpisodeNumberMapping:
    logger.debug(
        "Upserting episode mapping for slug={} abs={} S{}E{}",
        series_slug,
        absolute_number,
        season_number,
        episode_number,
    )
    _ensure_positive(absolute_number, "absolute_number")
    _ensure_positive(season_number, "season_number")
    _ensure_positive(episode_number, "episode_number")

    mapping = session.exec(
        select(EpisodeNumberMapping).where(
            (EpisodeNumberMapping.series_slug == series_slug)
            & (EpisodeNumberMapping.absolute_number == absolute_number)
        )
    ).first()

    if mapping is None:
        mapping = session.exec(
            select(EpisodeNumberMapping).where(
                (EpisodeNumberMapping.series_slug == series_slug)
                & (EpisodeNumberMapping.season_number == season_number)
                & (EpisodeNumberMapping.episode_number == episode_number)
            )
        ).first()

    if mapping is None:
        mapping = EpisodeNumberMapping(
            series_slug=series_slug,
            absolute_number=absolute_number,
            season_number=season_number,
            episode_number=episode_number,
            episode_title=episode_title,
            last_synced_at=as_aware_utc(last_synced_at) if last_synced_at else utcnow(),
        )
        session.add(mapping)
    else:
        mapping.absolute_number = absolute_number
        mapping.season_number = season_number
        mapping.episode_number = episode_number
        if episode_title is not None:
            mapping.episode_title = episode_title
        mapping.last_synced_at = as_aware_utc(last_synced_at) if last_synced_at else utcnow()
        session.add(mapping)

    try:
        session.commit()
        session.refresh(mapping)
        logger.success(
            "Upserted episode mapping slug={} abs={} S{}E{}",
            series_slug,
            absolute_number,
            season_number,
            episode_number,
        )
    except Exception as e:
        logger.error("Failed to upsert episode mapping: {}", e)
        session.rollback()
        raise
    return mapping


def get_episode_mapping_by_absolute(
    session: Session, *, series_slug: str, absolute_number: int
) -> Optional[EpisodeNumberMapping]:
    logger.debug(
        "Fetching episode mapping by absolute number slug={} abs={}",
        series_slug,
        absolute_number,
    )
    return session.exec(
        select(EpisodeNumberMapping).where(
            (EpisodeNumberMapping.series_slug == series_slug)
            & (EpisodeNumberMapping.absolute_number == absolute_number)
        )
    ).first()


def get_episode_mapping_by_season_episode(
    session: Session, *, series_slug: str, season_number: int, episode_number: int
) -> Optional[EpisodeNumberMapping]:
    logger.debug(
        "Fetching episode mapping by season/episode slug={} S{}E{}",
        series_slug,
        season_number,
        episode_number,
    )
    return session.exec(
        select(EpisodeNumberMapping).where(
            (EpisodeNumberMapping.series_slug == series_slug)
            & (EpisodeNumberMapping.season_number == season_number)
            & (EpisodeNumberMapping.episode_number == episode_number)
        )
    ).first()


def list_episode_mappings_for_series(
    session: Session, *, series_slug: str
) -> List[EpisodeNumberMapping]:
    logger.debug("Listing episode mappings for slug={}", series_slug)
    return session.exec(
        select(EpisodeNumberMapping)
        .where(EpisodeNumberMapping.series_slug == series_slug)
        .order_by(EpisodeNumberMapping.absolute_number)
    ).all()


# --- ClientTask CRUD
def upsert_client_task(
    session: Session,
    *,
    hash: str,
    name: str,
    slug: str,
    season: int,
    episode: int,
    absolute_number: Optional[int] = None,
    language: str,
    save_path: Optional[str],
    category: Optional[str],
    job_id: Optional[str],
    state: str = "queued",
) -> ClientTask:
    logger.debug(f"Upserting client task for hash {hash}")
    rec = session.get(ClientTask, hash)
    if rec is None:
        logger.info("No existing client task found, creating new.")
        rec = ClientTask(
            hash=hash,
            name=name,
            slug=slug,
            season=season,
            episode=episode,
            absolute_number=absolute_number,
            language=language,
            save_path=save_path,
            category=category,
            job_id=job_id,
            state=state,
        )
        session.add(rec)
    else:
        logger.info("Existing client task found, updating.")
        rec.name = name
        rec.slug = slug
        rec.season = season
        rec.episode = episode
        rec.absolute_number = absolute_number
        rec.language = language
        rec.save_path = save_path
        rec.category = category
        rec.job_id = job_id
        rec.state = state
        session.add(rec)
    try:
        session.commit()
        session.refresh(rec)
        logger.success(f"Upserted client task for hash {hash}")
    except Exception as e:
        logger.error(f"Failed to upsert client task: {e}")
        raise
    return rec


def get_client_task(session: Session, hash: str) -> Optional[ClientTask]:
    logger.debug(f"Fetching client task for hash {hash}")
    rec = session.get(ClientTask, hash)
    if rec:
        logger.debug("Client task found.")
    else:
        logger.warning("Client task not found.")
    return rec


def delete_client_task(session: Session, hash: str) -> None:
    logger.debug(f"Deleting client task for hash {hash}")
    rec = session.get(ClientTask, hash)
    if rec:
        session.delete(rec)
        session.commit()
        logger.success(f"Deleted client task for hash {hash}")
    else:
        logger.warning(f"Client task for hash {hash} not found, nothing to delete.")
