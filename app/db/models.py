from __future__ import annotations

from typing import Optional, Literal, Generator, Any, Dict, List, TYPE_CHECKING
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from loguru import logger
from fastapi import HTTPException

# Defer logger configuration to application startup

from sqlmodel import SQLModel, Field, Session, create_engine, select, Column, JSON
from sqlalchemy.orm import registry as sa_registry
from sqlalchemy.pool import NullPool

if TYPE_CHECKING:
    from alembic.config import Config

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
        """
        Determine whether this availability record is still fresh according to AVAILABILITY_TTL_HOURS.

        If AVAILABILITY_TTL_HOURS is less than or equal to zero the record is considered always fresh. Freshness is determined by comparing the time since `checked_at` to the TTL.

        Returns:
            `true` if the time since `checked_at` is less than or equal to AVAILABILITY_TTL_HOURS, `false` otherwise.
        """
        logger.debug(
            f"Checking freshness for {self.slug} S{self.season}E{self.episode} {self.language}"
        )
        if AVAILABILITY_TTL_HOURS <= 0:
            logger.info("AVAILABILITY_TTL_HOURS <= 0, always fresh.")
            return True
        age = as_aware_utc(utcnow()) - as_aware_utc(self.checked_at)
        logger.debug(f"Age of availability: {age}")
        return age <= timedelta(hours=AVAILABILITY_TTL_HOURS)


# ---------------- STRM Proxy URL Mapping
class StrmUrlMapping(ModelBase, table=True):
    """
    Persistent mapping of episode identity to resolved upstream URLs for STRM proxying.

    The provider field is stored as a non-nullable string to allow composite primary
    key usage even when no provider hint is supplied (empty string = no provider).
    """

    site: str = Field(default="aniworld.to", primary_key=True)
    slug: str = Field(primary_key=True)
    season: int = Field(primary_key=True)
    episode: int = Field(primary_key=True)
    language: str = Field(primary_key=True)
    provider: str = Field(default="", primary_key=True)

    resolved_url: str
    provider_used: Optional[str] = None
    resolved_headers: Optional[dict[str, Any]] = Field(
        sa_column=Column(JSON), default=None
    )
    resolved_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)


# ---------------- qBittorrent-Shim: ClientTask
class ClientTask(ModelBase, table=True):
    """
    Abbildung eines „Torrents“ (Magnet) auf unseren internen Job.
    """

    hash: str = Field(
        primary_key=True, index=True
    )  # corresponds to BTIH (from magnet 'xt' parameter)
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


# ---------------- Engine and Session utilities
DATABASE_URL = f"sqlite:///{(DATA_DIR / 'anibridge_jobs.db').as_posix()}"
logger.debug(f"DATABASE_URL: {DATABASE_URL}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=NullPool,  # ensure connections are closed when sessions end
)
logger.debug("SQLModel engine created.")

MIGRATION_BASE_REVISION = "20260203_0001"


def _get_alembic_config() -> "Config":
    from pathlib import Path
    from alembic.config import Config

    config_path: Path | None = None
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "alembic.ini"
        if candidate.exists():
            config_path = candidate
            break

    if config_path is not None:
        config = Config(str(config_path))
    else:
        logger.warning("Alembic config not found; using defaults.")
        config = Config()

    migrations_path = Path(__file__).resolve().parent / "migrations"
    config.set_main_option("script_location", str(migrations_path))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    return config


def apply_migrations() -> None:
    """
    Apply Alembic migrations, including a bootstrap step for legacy databases
    that predate Alembic versioning.
    """
    from alembic import command
    from sqlalchemy import inspect

    logger.debug("Applying DB migrations.")
    try:
        config = _get_alembic_config()
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        has_version = "alembic_version" in tables
        data_tables = tables - {"alembic_version"}

        if not has_version:
            if not tables:
                command.upgrade(config, "head")
                logger.success("Database created via Alembic migrations.")
                return

            logger.info("Legacy database detected; stamping base revision.")
            command.stamp(config, MIGRATION_BASE_REVISION)
        else:
            with engine.begin() as conn:
                rows = conn.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).fetchall()
            versions = [row[0] for row in rows if row and row[0]]
            if not versions:
                if data_tables:
                    logger.info(
                        "Alembic version table is empty; stamping base revision "
                        "for legacy database."
                    )
                    command.stamp(config, MIGRATION_BASE_REVISION)
                else:
                    logger.info(
                        "Alembic version table is empty with no data tables; "
                        "treating as fresh database."
                    )

        command.upgrade(config, "head")
        logger.success("Database migrations complete.")
    except Exception as e:
        logger.error(f"Error applying DB migrations: {e}")
        raise


def create_db_and_tables() -> None:
    """Create tables directly without running Alembic migrations."""
    logger.debug("Creating DB and tables if not exist (no migrations).")
    try:
        ModelBase.metadata.create_all(engine)
        logger.success("Database and tables created or already exist.")
    except Exception as e:
        logger.error(f"Error creating DB and tables: {e}")
        raise


def get_session() -> Generator[Session, None, None]:
    logger.debug("Creating new DB session.")
    try:
        with Session(engine) as session:
            logger.debug("DB session created.")
            yield session
    except HTTPException:
        raise
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
    rows = session.exec(
        select(Job).where(Job.status.in_(["queued", "downloading"]))
    ).all()  # type: ignore
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
            & EpisodeAvailability.available
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


# --- STRM URL Mapping CRUD
def get_strm_mapping(
    session: Session,
    *,
    site: str,
    slug: str,
    season: int,
    episode: int,
    language: str,
    provider: Optional[str] = None,
) -> Optional[StrmUrlMapping]:
    """
    Fetch the STRM URL mapping for the specified episode identity and optional provider hint.

    Parameters:
        provider (Optional[str]): Preferred provider hint; treated as the empty string when not provided.

    Returns:
        Optional[StrmUrlMapping]: The matching StrmUrlMapping record if found, `None` otherwise.
    """
    key = (site, slug, season, episode, language, provider or "")
    logger.debug("Fetching STRM mapping for {}", key)
    rec = session.get(StrmUrlMapping, key)
    if rec:
        logger.debug("STRM mapping found.")
    else:
        logger.debug("STRM mapping not found.")
    return rec


def upsert_strm_mapping(
    session: Session,
    *,
    site: str,
    slug: str,
    season: int,
    episode: int,
    language: str,
    provider: Optional[str],
    resolved_url: str,
    provider_used: Optional[str] = None,
    resolved_headers: Optional[Dict[str, Any]] = None,
) -> StrmUrlMapping:
    """
    Create or update a STRM URL mapping for a specific (site, slug, season, episode, language, provider) key and persist it.

    Parameters:
        session: Database session used to load and persist the mapping.
        site (str): Site identifier (part of the composite key).
        slug (str): Content slug (part of the composite key).
        season (int): Season number (part of the composite key).
        episode (int): Episode number (part of the composite key).
        language (str): Language code (part of the composite key).
        provider (Optional[str]): Provider identifier (part of the composite key). If `None`, an empty string is used for the key.
        resolved_url (str): The resolved stream URL to store.
        provider_used (Optional[str]): The provider that was actually used to resolve `resolved_url`.
        resolved_headers (Optional[dict]): Optional headers associated with the resolved URL; stored as JSON.

    Returns:
        StrmUrlMapping: The persisted mapping instance with `resolved_at` and `updated_at` set to the current UTC time.
    """
    key = (site, slug, season, episode, language, provider or "")
    logger.debug("Upserting STRM mapping for {}", key)
    rec = session.get(StrmUrlMapping, key)
    if rec is None:
        logger.info("No existing STRM mapping found, creating new.")
        rec = StrmUrlMapping(
            site=site,
            slug=slug,
            season=season,
            episode=episode,
            language=language,
            provider=provider or "",
            resolved_url=resolved_url,
            provider_used=provider_used,
            resolved_headers=resolved_headers,
            resolved_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(rec)
    else:
        logger.info("Existing STRM mapping found, updating.")
        rec.resolved_url = resolved_url
        rec.provider_used = provider_used
        rec.resolved_headers = resolved_headers
        rec.resolved_at = utcnow()
        rec.updated_at = utcnow()
        session.add(rec)
    try:
        session.commit()
        session.refresh(rec)
        logger.success("Upserted STRM mapping for {}", key)
    except Exception as e:
        logger.error(f"Failed to upsert STRM mapping: {e}")
        raise
    return rec


def delete_strm_mapping(
    session: Session,
    *,
    site: str,
    slug: str,
    season: int,
    episode: int,
    language: str,
    provider: Optional[str] = None,
) -> None:
    """
    Delete the STRM URL mapping identified by the composite key if it exists.

    If `provider` is `None`, it is treated as the empty string when looking up the mapping. The deletion is committed to the database; if no matching mapping is found the function does nothing.
    Parameters:
        provider (Optional[str]): Provider identifier; use `None` to match the empty-string provider key.
    """
    key = (site, slug, season, episode, language, provider or "")
    logger.debug("Deleting STRM mapping for {}", key)
    rec = session.get(StrmUrlMapping, key)
    if rec:
        session.delete(rec)
        session.commit()
        logger.success("Deleted STRM mapping for {}", key)
    else:
        logger.debug("No STRM mapping found for {}", key)


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
    Insert or update a ClientTask record identified by its hash.

    Parameters:
        hash (str): Unique identifier for the client task (primary key).
        site (str): Site identifier to store on the record; defaults to "aniworld.to".

    Returns:
        ClientTask: The persisted ClientTask instance refreshed from the database.
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
