"""Database models for AniBridge.

This module defines the SQLModel table models used throughout the application.
All models inherit from ModelBase (defined in app.db.base) to ensure consistent
metadata and registry usage, which is critical for Alembic migrations.

Models:
    - Job: Tracks download job status and progress
    - EpisodeAvailability: Caches episode availability information
    - ClientTask: Maps qBittorrent-style torrent hashes to internal jobs

To add a new model:
    1. Import ModelBase from app.db.base
    2. Define your model class inheriting from ModelBase with table=True
    3. Add appropriate fields with SQLModel Field() annotations
    4. Generate a new migration: alembic revision --autogenerate -m "Add MyModel"
    5. Review and apply: alembic upgrade head
"""

from __future__ import annotations

from typing import Optional, Literal, Any, List
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from loguru import logger

from sqlmodel import Field, Session, select, Column, JSON

from app.config import AVAILABILITY_TTL_HOURS
from app.db.base import ModelBase
from app.db.session import engine

JobStatus = Literal["queued", "downloading", "completed", "failed", "cancelled"]


# ---- Datetime Helpers
def utcnow() -> datetime:
    """Return current UTC datetime with timezone info."""
    logger.debug("utcnow() called.")
    return datetime.now(timezone.utc)


def as_aware_utc(dt: Optional[datetime]) -> datetime:
    """Convert a datetime to timezone-aware UTC.

    Args:
        dt: Datetime to convert (can be None, naive, or aware)

    Returns:
        Timezone-aware UTC datetime
    """
    logger.debug(f"as_aware_utc() called with dt={dt}")
    if dt is None:
        logger.info("Datetime is None, returning utcnow().")
        return utcnow()
    if dt.tzinfo is None:
        logger.info("Datetime is naive, setting tzinfo to UTC.")
        return dt.replace(tzinfo=timezone.utc)
    logger.info("Datetime is aware, converting to UTC.")
    return dt.astimezone(timezone.utc)


# ---------------- Table Models


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
    source_site: Optional[str] = Field(
        default="aniworld.to", index=True
    )  # Track originating site

    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)


# ---------------- Semi-Cache: Episode Availability
class EpisodeAvailability(ModelBase, table=True):
    """
    Semi-Cache: pro (slug, season, episode, language, site) speichern wir:
      - height/vcodec (aus Preflight-Probe)
      - available (bool): Sprache wirklich verfügbar?
      - provider (optional): welcher Provider hat funktioniert
      - checked_at: wann zuletzt geprüft
      - site: which catalogue site this episode is from (aniworld.to or s.to)
    """

    slug: str = Field(primary_key=True)
    season: int = Field(primary_key=True)
    episode: int = Field(primary_key=True)
    language: str = Field(primary_key=True)
    site: str = Field(
        default="aniworld.to", primary_key=True
    )  # Add site to primary key
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
    language: str
    site: Optional[str] = Field(default="aniworld.to", index=True)  # Track source site
    job_id: Optional[str] = Field(default=None, index=True)
    save_path: Optional[str] = None
    category: Optional[str] = None
    added_on: datetime = Field(default_factory=utcnow, index=True)
    completion_on: Optional[datetime] = None
    state: str = Field(
        default="queued", index=True
    )  # queued/downloading/paused/completed/error


# ---------------- Database Initialization (now handled by Alembic)

# NOTE: The old _migrate_episode_availability_table() and create_db_and_tables()
# functions have been removed. Database schema is now managed by Alembic migrations.
#
# To initialize the database:
#   1. Run: alembic upgrade head
#
# To create a new migration after model changes:
#   1. Edit models in this file
#   2. Run: alembic revision --autogenerate -m "Description of changes"
#   3. Review the generated migration in alembic/versions/
#   4. Apply: alembic upgrade head


# ---------------- CRUD Helper Functions
def create_job(session: Session, *, source_site: Optional[str] = None) -> Job:
    """
    Create and persist a new Job record in the database.

    Parameters:
        source_site (Optional[str]): Optional source site identifier to associate with the job; if omitted the model's default is used.

    Returns:
        Job: The created Job instance refreshed from the database (includes generated id and timestamps).
    """
    logger.debug("Creating new job entry in DB.")
    try:
        job_kwargs: dict[str, Any] = {}
        if source_site:
            job_kwargs["source_site"] = source_site
        job = Job(**job_kwargs)
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
    site: str = "aniworld.to",
) -> EpisodeAvailability:
    """
    Create or update the cached availability record for a specific episode/language on a site and persist the result.

    Parameters:
        session (Session): Database session used to read and persist the record.
        slug (str): Series identifier.
        season (int): Season number.
        episode (int): Episode number.
        language (str): Language code for the availability entry.
        available (bool): Whether the episode is available.
        height (Optional[int]): Video height in pixels, or `None` if unknown.
        vcodec (Optional[str]): Video codec identifier, or `None` if unknown.
        provider (Optional[str]): Provider name/source, or `None` if unknown.
        extra (Optional[dict]): Optional auxiliary metadata for the record.
        site (str): Site identifier to scope the availability entry.

    Returns:
        EpisodeAvailability: The persisted availability record reflecting the created or updated state.
    """
    logger.debug(
        f"Upserting availability for {slug} S{season}E{episode} {language} on {site}"
    )
    rec = session.get(EpisodeAvailability, (slug, season, episode, language, site))
    if rec is None:
        logger.info("No existing availability record found, creating new.")
        rec = EpisodeAvailability(
            slug=slug,
            season=season,
            episode=episode,
            language=language,
            site=site,
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
            f"Upserted availability for {slug} S{season}E{episode} {language} on {site}"
        )
    except Exception as e:
        logger.error(f"Failed to upsert availability: {e}")
        raise
    return rec


def get_availability(
    session: Session,
    *,
    slug: str,
    season: int,
    episode: int,
    language: str,
    site: str = "aniworld.to",
) -> Optional[EpisodeAvailability]:
    """
    Retrieve the cached availability record for a specific episode identified by slug, season, episode, language, and site.

    Parameters:
        site (str): Site identifier to query for (default "aniworld.to").

    Returns:
        EpisodeAvailability | None: `EpisodeAvailability` if a matching record exists, `None` otherwise.
    """
    logger.debug(
        f"Fetching availability for {slug} S{season}E{episode} {language} on {site}"
    )
    rec = session.get(EpisodeAvailability, (slug, season, episode, language, site))
    if rec:
        logger.debug("Availability record found.")
    else:
        logger.warning("Availability record not found.")
    return rec


def list_available_languages_cached(
    session: Session, *, slug: str, season: int, episode: int, site: str = "aniworld.to"
) -> List[str]:
    """
    List languages with fresh cached availability for a specific episode on a site.

    Parameters:
        slug (str): Episode/series identifier used to look up availability.
        season (int): Season number of the episode.
        episode (int): Episode number within the season.
        site (str): Site identifier to scope the availability records (defaults to "aniworld.to").

    Returns:
        List[str]: Languages that have a cached availability record considered fresh.
    """
    logger.debug(
        f"Listing available cached languages for {slug} S{season}E{episode} on {site}"
    )
    rows = session.exec(
        select(EpisodeAvailability).where(
            (EpisodeAvailability.slug == slug)
            & (EpisodeAvailability.season == season)
            & (EpisodeAvailability.episode == episode)
            & (EpisodeAvailability.site == site)
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


# --- ClientTask CRUD
def upsert_client_task(
    session: Session,
    *,
    hash: str,
    name: str,
    slug: str,
    season: int,
    episode: int,
    language: str,
    save_path: Optional[str],
    category: Optional[str],
    job_id: Optional[str],
    state: str = "queued",
    site: str = "aniworld.to",
) -> ClientTask:
    """
    Create or update a ClientTask record for the given torrent/file hash.

    Parameters:
        hash (str): Unique identifier for the client task (primary key).
        site (str): Site identifier to store on the record; defaults to "aniworld.to".

    Returns:
        ClientTask: The inserted or updated ClientTask instance refreshed from the database.
    """
    logger.debug(f"Upserting client task for hash {hash} on site {site}")
    rec = session.get(ClientTask, hash)
    if rec is None:
        logger.info("No existing client task found, creating new.")
        rec = ClientTask(
            hash=hash,
            name=name,
            slug=slug,
            season=season,
            episode=episode,
            language=language,
            site=site,
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
        rec.language = language
        rec.site = site
        rec.save_path = save_path
        rec.category = category
        rec.job_id = job_id
        rec.state = state
        session.add(rec)
    try:
        session.commit()
        session.refresh(rec)
        logger.success(f"Upserted client task for hash {hash} on site {site}")
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
