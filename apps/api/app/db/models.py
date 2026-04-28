from __future__ import annotations

from typing import Optional, Literal, Generator, Any, Dict, List, TYPE_CHECKING
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import re
import unicodedata
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
CatalogRefreshStatus = Literal[
    "pending",
    "running",
    "ready",
    "failed",
]
CatalogMappingConfidence = Literal[
    "confirmed",
    "high_confidence",
    "low_confidence",
    "unresolved",
    "conflict",
]


# ---- Datetime Helpers
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_aware_utc(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return utcnow()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
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


# ---------------- Provider Catalog Index
class ProviderIndexStatus(ModelBase, table=True):
    provider: str = Field(primary_key=True)
    refresh_interval_hours: float = 24.0
    status: str = Field(default="pending", index=True)
    current_generation: Optional[str] = None
    latest_success_generation: Optional[str] = None
    latest_started_at: Optional[datetime] = Field(default=None, index=True)
    latest_completed_at: Optional[datetime] = Field(default=None, index=True)
    latest_success_at: Optional[datetime] = Field(default=None, index=True)
    next_refresh_after: Optional[datetime] = Field(default=None, index=True)
    bootstrap_completed: bool = Field(default=False, index=True)
    failure_count: int = 0
    last_error_summary: Optional[str] = None
    cursor_title_slug: Optional[str] = None
    updated_at: datetime = Field(default_factory=utcnow, index=True)


class ProviderTitleIndexState(ModelBase, table=True):
    provider: str = Field(primary_key=True)
    slug: str = Field(primary_key=True)
    last_attempted_at: Optional[datetime] = Field(default=None, index=True)
    last_success_at: Optional[datetime] = Field(default=None, index=True)
    failure_count: int = 0
    last_error_summary: Optional[str] = None
    updated_at: datetime = Field(default_factory=utcnow, index=True)


class ProviderCatalogTitle(ModelBase, table=True):
    provider: str = Field(primary_key=True)
    slug: str = Field(primary_key=True)
    title: str = Field(index=True)
    normalized_title: str = Field(index=True)
    media_type_hint: str = Field(default="series", index=True)
    relative_path: str
    indexed_generation: str = Field(index=True)
    last_indexed_at: datetime = Field(default_factory=utcnow, index=True)


class ProviderCatalogAlias(ModelBase, table=True):
    provider: str = Field(primary_key=True)
    slug: str = Field(primary_key=True)
    alias: str = Field(primary_key=True)
    normalized_alias: str = Field(index=True)
    indexed_generation: str = Field(index=True)
    last_indexed_at: datetime = Field(default_factory=utcnow, index=True)


class ProviderCatalogEpisode(ModelBase, table=True):
    provider: str = Field(primary_key=True)
    slug: str = Field(primary_key=True)
    season: int = Field(primary_key=True)
    episode: int = Field(primary_key=True)
    title_primary: Optional[str] = None
    title_secondary: Optional[str] = None
    relative_path: str
    media_type_hint: str = Field(default="episode", index=True)
    indexed_generation: str = Field(index=True)
    last_indexed_at: datetime = Field(default_factory=utcnow, index=True)


class ProviderEpisodeLanguage(ModelBase, table=True):
    provider: str = Field(primary_key=True)
    slug: str = Field(primary_key=True)
    season: int = Field(primary_key=True)
    episode: int = Field(primary_key=True)
    language: str = Field(primary_key=True)
    normalized_language: str = Field(index=True)
    host_hints: Optional[list[str]] = Field(sa_column=Column(JSON), default=None)
    indexed_generation: str = Field(index=True)
    last_indexed_at: datetime = Field(default_factory=utcnow, index=True)


class CanonicalSeries(ModelBase, table=True):
    tvdb_id: int = Field(primary_key=True)
    title: str = Field(index=True)
    normalized_title: str = Field(index=True)
    tmdb_id: Optional[int] = Field(default=None, index=True)
    imdb_id: Optional[str] = Field(default=None, index=True)
    tvmaze_id: Optional[int] = Field(default=None, index=True)
    anilist_id: Optional[int] = Field(default=None, index=True)
    mal_id: Optional[int] = Field(default=None, index=True)
    last_synced_at: datetime = Field(default_factory=utcnow, index=True)


class CanonicalSeriesAlias(ModelBase, table=True):
    tvdb_id: int = Field(primary_key=True)
    alias: str = Field(primary_key=True)
    normalized_alias: str = Field(index=True)


class CanonicalEpisode(ModelBase, table=True):
    tvdb_id: int = Field(primary_key=True)
    season: int = Field(primary_key=True)
    episode: int = Field(primary_key=True)
    title: str = Field(index=True)
    normalized_title: str = Field(index=True)
    last_synced_at: datetime = Field(default_factory=utcnow, index=True)


class CanonicalMovie(ModelBase, table=True):
    tmdb_id: int = Field(primary_key=True)
    title: str = Field(index=True)
    normalized_title: str = Field(index=True)
    release_year: int = Field(index=True)
    imdb_id: Optional[str] = Field(default=None, index=True)
    tvdb_id: Optional[int] = Field(default=None, index=True)
    last_synced_at: datetime = Field(default_factory=utcnow, index=True)


class ProviderSeriesMapping(ModelBase, table=True):
    provider: str = Field(primary_key=True)
    slug: str = Field(primary_key=True)
    tvdb_id: int = Field(primary_key=True)
    confidence: str = Field(default="unresolved", index=True)
    source: str = Field(default="title_match", index=True)
    rationale: Optional[str] = None
    last_verified_at: datetime = Field(default_factory=utcnow, index=True)


class ProviderEpisodeMapping(ModelBase, table=True):
    provider: str = Field(primary_key=True)
    slug: str = Field(primary_key=True)
    provider_season: int = Field(primary_key=True)
    provider_episode: int = Field(primary_key=True)
    tvdb_id: int = Field(primary_key=True)
    canonical_season: int = Field(primary_key=True)
    canonical_episode: int = Field(primary_key=True)
    confidence: str = Field(default="unresolved", index=True)
    source: str = Field(default="numbering", index=True)
    rationale: Optional[str] = None
    last_verified_at: datetime = Field(default_factory=utcnow, index=True)


class ProviderMovieMapping(ModelBase, table=True):
    provider: str = Field(primary_key=True)
    slug: str = Field(primary_key=True)
    tmdb_id: int = Field(primary_key=True)
    confidence: str = Field(default="unresolved", index=True)
    source: str = Field(default="title_year", index=True)
    rationale: Optional[str] = None
    last_verified_at: datetime = Field(default_factory=utcnow, index=True)


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
    logger.trace(f"Fetching job {job_id} from DB.")
    job = session.get(Job, job_id)
    if job:
        logger.trace(f"Job {job_id} found.")
    else:
        logger.warning(f"Job {job_id} not found.")
    return job


def update_job(session: Session, job_id: str, **fields: Any) -> Optional[Job]:
    logger.trace(f"Updating job {job_id} with fields {fields}")
    job = session.get(Job, job_id)
    if not job:
        logger.warning(f"Job {job_id} not found for update.")
        return None
    for k, v in fields.items():
        logger.trace(f"Setting {k} to {v} for job {job_id}")
        setattr(job, k, v)
    job.updated_at = utcnow()
    session.add(job)
    try:
        session.commit()
        session.refresh(job)
        # Avoid console spam on frequent progress updates
        logger.trace(f"Updated job {job_id}")
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


def list_cached_episode_numbers_for_season(
    session: Session, *, slug: str, season: int, site: str = "aniworld.to"
) -> List[int]:
    """
    List distinct episode numbers with positive cached availability for a season.

    Parameters:
        slug (str): Episode/series identifier used to look up availability rows.
        season (int): Season number to scan.
        site (str): Site identifier to scope records (defaults to "aniworld.to").

    Returns:
        List[int]: Sorted distinct episode numbers that have `available=True`.
    """
    logger.debug(
        "Listing cached episode numbers for slug={} season={} site={}",
        slug,
        season,
        site,
    )
    rows = session.exec(
        select(EpisodeAvailability.episode).where(
            (EpisodeAvailability.slug == slug)
            & (EpisodeAvailability.season == season)
            & (EpisodeAvailability.site == site)
            & EpisodeAvailability.available
        )
    ).all()
    unique_episode_numbers: set[int] = set()
    for episode_no in rows:
        try:
            parsed = int(episode_no)
        except TypeError, ValueError:
            continue
        if parsed > 0:
            unique_episode_numbers.add(parsed)
    episodes = sorted(unique_episode_numbers)
    logger.debug(
        "Cached episode numbers for slug={} season={} site={}: {}",
        slug,
        season,
        site,
        episodes,
    )
    return episodes


def normalize_catalog_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.replace("’", "'").replace("`", "'")
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", normalized)
    return normalized.lower().strip()


def upsert_provider_index_status(
    session: Session,
    *,
    provider: str,
    refresh_interval_hours: float,
    status: Optional[str] = None,
    current_generation: Optional[str] = None,
    latest_success_generation: Optional[str] = None,
    latest_started_at: Optional[datetime] = None,
    latest_completed_at: Optional[datetime] = None,
    latest_success_at: Optional[datetime] = None,
    next_refresh_after: Optional[datetime] = None,
    bootstrap_completed: Optional[bool] = None,
    failure_count: Optional[int] = None,
    last_error_summary: Optional[str] = None,
    cursor_title_slug: Optional[str] = None,
) -> ProviderIndexStatus:
    rec = session.get(ProviderIndexStatus, provider)
    if rec is None:
        rec = ProviderIndexStatus(
            provider=provider,
            refresh_interval_hours=refresh_interval_hours,
        )
    rec.refresh_interval_hours = refresh_interval_hours
    if status is not None:
        rec.status = status
    if current_generation is not None:
        rec.current_generation = current_generation
    if latest_success_generation is not None:
        rec.latest_success_generation = latest_success_generation
    if latest_started_at is not None:
        rec.latest_started_at = latest_started_at
    if latest_completed_at is not None:
        rec.latest_completed_at = latest_completed_at
    if latest_success_at is not None:
        rec.latest_success_at = latest_success_at
    if next_refresh_after is not None:
        rec.next_refresh_after = next_refresh_after
    if bootstrap_completed is not None:
        rec.bootstrap_completed = bootstrap_completed
    if failure_count is not None:
        rec.failure_count = failure_count
    if last_error_summary is not None:
        rec.last_error_summary = last_error_summary
    if cursor_title_slug is not None or status == "ready":
        rec.cursor_title_slug = cursor_title_slug
    rec.updated_at = utcnow()
    session.add(rec)
    session.commit()
    session.refresh(rec)
    return rec


def get_provider_index_status(
    session: Session,
    *,
    provider: str,
) -> Optional[ProviderIndexStatus]:
    return session.get(ProviderIndexStatus, provider)


def list_provider_index_statuses(session: Session) -> List[ProviderIndexStatus]:
    return list(session.exec(select(ProviderIndexStatus)).all())


def upsert_provider_title_index_state(
    session: Session,
    *,
    provider: str,
    slug: str,
    attempted_at: Optional[datetime] = None,
    succeeded_at: Optional[datetime] = None,
    failure_count: Optional[int] = None,
    last_error_summary: Optional[str] = None,
) -> ProviderTitleIndexState:
    rec = session.get(ProviderTitleIndexState, (provider, slug))
    if rec is None:
        rec = ProviderTitleIndexState(provider=provider, slug=slug)
    if attempted_at is not None:
        rec.last_attempted_at = attempted_at
    if succeeded_at is not None:
        rec.last_success_at = succeeded_at
    if failure_count is not None:
        rec.failure_count = failure_count
    if last_error_summary is not None:
        rec.last_error_summary = last_error_summary
    rec.updated_at = utcnow()
    session.add(rec)
    session.commit()
    session.refresh(rec)
    return rec


def replace_provider_catalog_title(
    session: Session,
    *,
    provider: str,
    slug: str,
    title: str,
    media_type_hint: str,
    relative_path: str,
    indexed_generation: str,
) -> ProviderCatalogTitle:
    rec = session.get(ProviderCatalogTitle, (provider, slug))
    if rec is None:
        rec = ProviderCatalogTitle(
            provider=provider,
            slug=slug,
            title=title,
            normalized_title=normalize_catalog_text(title),
            media_type_hint=media_type_hint,
            relative_path=relative_path,
            indexed_generation=indexed_generation,
            last_indexed_at=utcnow(),
        )
    else:
        rec.title = title
        rec.normalized_title = normalize_catalog_text(title)
        rec.media_type_hint = media_type_hint
        rec.relative_path = relative_path
        rec.indexed_generation = indexed_generation
        rec.last_indexed_at = utcnow()
    session.add(rec)
    return rec


def replace_provider_catalog_aliases(
    session: Session,
    *,
    provider: str,
    slug: str,
    aliases: List[str],
    indexed_generation: str,
) -> None:
    session.exec(
        select(ProviderCatalogAlias).where(
            (ProviderCatalogAlias.provider == provider)
            & (ProviderCatalogAlias.slug == slug)
        )
    ).all()
    session.exec(
        ProviderCatalogAlias.__table__.delete().where(
            (ProviderCatalogAlias.provider == provider)
            & (ProviderCatalogAlias.slug == slug)
        )
    )
    seen: set[str] = set()
    for alias in aliases:
        alias_clean = (alias or "").strip()
        if not alias_clean or alias_clean in seen:
            continue
        seen.add(alias_clean)
        session.add(
            ProviderCatalogAlias(
                provider=provider,
                slug=slug,
                alias=alias_clean,
                normalized_alias=normalize_catalog_text(alias_clean),
                indexed_generation=indexed_generation,
                last_indexed_at=utcnow(),
            )
        )


def replace_provider_catalog_episodes(
    session: Session,
    *,
    provider: str,
    slug: str,
    episodes: List[dict[str, Any]],
    indexed_generation: str,
) -> None:
    session.exec(
        ProviderEpisodeLanguage.__table__.delete().where(
            (ProviderEpisodeLanguage.provider == provider)
            & (ProviderEpisodeLanguage.slug == slug)
        )
    )
    session.exec(
        ProviderCatalogEpisode.__table__.delete().where(
            (ProviderCatalogEpisode.provider == provider)
            & (ProviderCatalogEpisode.slug == slug)
        )
    )
    for item in episodes:
        session.add(
            ProviderCatalogEpisode(
                provider=provider,
                slug=slug,
                season=int(item["season"]),
                episode=int(item["episode"]),
                title_primary=item.get("title_primary"),
                title_secondary=item.get("title_secondary"),
                relative_path=item["relative_path"],
                media_type_hint=item.get("media_type_hint", "episode"),
                indexed_generation=indexed_generation,
                last_indexed_at=utcnow(),
            )
        )
        for language_payload in item.get("languages", []):
            language = str(language_payload.get("language") or "").strip()
            if not language:
                continue
            session.add(
                ProviderEpisodeLanguage(
                    provider=provider,
                    slug=slug,
                    season=int(item["season"]),
                    episode=int(item["episode"]),
                    language=language,
                    normalized_language=normalize_catalog_text(language),
                    host_hints=list(language_payload.get("host_hints") or []),
                    indexed_generation=indexed_generation,
                    last_indexed_at=utcnow(),
                )
            )


def prune_provider_generation(
    session: Session,
    *,
    provider: str,
    keep_generation: str,
) -> None:
    session.exec(
        ProviderCatalogAlias.__table__.delete().where(
            (ProviderCatalogAlias.provider == provider)
            & (ProviderCatalogAlias.indexed_generation != keep_generation)
        )
    )
    session.exec(
        ProviderEpisodeLanguage.__table__.delete().where(
            (ProviderEpisodeLanguage.provider == provider)
            & (ProviderEpisodeLanguage.indexed_generation != keep_generation)
        )
    )
    session.exec(
        ProviderCatalogEpisode.__table__.delete().where(
            (ProviderCatalogEpisode.provider == provider)
            & (ProviderCatalogEpisode.indexed_generation != keep_generation)
        )
    )
    session.exec(
        ProviderCatalogTitle.__table__.delete().where(
            (ProviderCatalogTitle.provider == provider)
            & (ProviderCatalogTitle.indexed_generation != keep_generation)
        )
    )
    session.commit()


def delete_provider_generation(
    session: Session,
    *,
    provider: str,
    generation: str,
) -> None:
    session.exec(
        ProviderCatalogAlias.__table__.delete().where(
            (ProviderCatalogAlias.provider == provider)
            & (ProviderCatalogAlias.indexed_generation == generation)
        )
    )
    session.exec(
        ProviderEpisodeLanguage.__table__.delete().where(
            (ProviderEpisodeLanguage.provider == provider)
            & (ProviderEpisodeLanguage.indexed_generation == generation)
        )
    )
    session.exec(
        ProviderCatalogEpisode.__table__.delete().where(
            (ProviderCatalogEpisode.provider == provider)
            & (ProviderCatalogEpisode.indexed_generation == generation)
        )
    )
    session.exec(
        ProviderCatalogTitle.__table__.delete().where(
            (ProviderCatalogTitle.provider == provider)
            & (ProviderCatalogTitle.indexed_generation == generation)
        )
    )
    session.commit()


def _visible_generation_map(
    session: Session,
    *,
    providers: List[str],
) -> dict[str, str]:
    rows = session.exec(
        select(ProviderIndexStatus).where(ProviderIndexStatus.provider.in_(providers))
    ).all()
    return {
        row.provider: row.latest_success_generation
        for row in rows
        if row.latest_success_generation
    }


def replace_provider_series_mappings(
    session: Session,
    *,
    provider: str,
    slug: str,
    mappings: List[dict[str, Any]],
) -> None:
    session.exec(
        ProviderSeriesMapping.__table__.delete().where(
            (ProviderSeriesMapping.provider == provider)
            & (ProviderSeriesMapping.slug == slug)
        )
    )
    for mapping in mappings:
        session.add(
            ProviderSeriesMapping(
                provider=provider,
                slug=slug,
                tvdb_id=int(mapping["tvdb_id"]),
                confidence=str(mapping.get("confidence", "unresolved")),
                source=str(mapping.get("source", "title_match")),
                rationale=mapping.get("rationale"),
                last_verified_at=utcnow(),
            )
        )


def replace_provider_episode_mappings(
    session: Session,
    *,
    provider: str,
    slug: str,
    mappings: List[dict[str, Any]],
) -> None:
    session.exec(
        ProviderEpisodeMapping.__table__.delete().where(
            (ProviderEpisodeMapping.provider == provider)
            & (ProviderEpisodeMapping.slug == slug)
        )
    )
    for mapping in mappings:
        session.add(
            ProviderEpisodeMapping(
                provider=provider,
                slug=slug,
                provider_season=int(mapping["provider_season"]),
                provider_episode=int(mapping["provider_episode"]),
                tvdb_id=int(mapping["tvdb_id"]),
                canonical_season=int(mapping["canonical_season"]),
                canonical_episode=int(mapping["canonical_episode"]),
                confidence=str(mapping.get("confidence", "unresolved")),
                source=str(mapping.get("source", "numbering")),
                rationale=mapping.get("rationale"),
                last_verified_at=utcnow(),
            )
        )


def replace_provider_movie_mappings(
    session: Session,
    *,
    provider: str,
    slug: str,
    mappings: List[dict[str, Any]],
) -> None:
    session.exec(
        ProviderMovieMapping.__table__.delete().where(
            (ProviderMovieMapping.provider == provider)
            & (ProviderMovieMapping.slug == slug)
        )
    )
    for mapping in mappings:
        session.add(
            ProviderMovieMapping(
                provider=provider,
                slug=slug,
                tmdb_id=int(mapping["tmdb_id"]),
                confidence=str(mapping.get("confidence", "unresolved")),
                source=str(mapping.get("source", "title_year")),
                rationale=mapping.get("rationale"),
                last_verified_at=utcnow(),
            )
        )


def upsert_canonical_series(
    session: Session,
    *,
    tvdb_id: int,
    title: str,
    tmdb_id: Optional[int] = None,
    imdb_id: Optional[str] = None,
    tvmaze_id: Optional[int] = None,
    anilist_id: Optional[int] = None,
    mal_id: Optional[int] = None,
    aliases: Optional[List[str]] = None,
) -> CanonicalSeries:
    rec = session.get(CanonicalSeries, tvdb_id)
    if rec is None:
        rec = CanonicalSeries(tvdb_id=tvdb_id, title=title, normalized_title="")
    rec.title = title
    rec.normalized_title = normalize_catalog_text(title)
    rec.tmdb_id = tmdb_id
    rec.imdb_id = imdb_id
    rec.tvmaze_id = tvmaze_id
    rec.anilist_id = anilist_id
    rec.mal_id = mal_id
    rec.last_synced_at = utcnow()
    session.add(rec)
    session.exec(
        CanonicalSeriesAlias.__table__.delete().where(
            CanonicalSeriesAlias.tvdb_id == tvdb_id
        )
    )
    for alias in aliases or []:
        alias_clean = (alias or "").strip()
        if not alias_clean:
            continue
        session.add(
            CanonicalSeriesAlias(
                tvdb_id=tvdb_id,
                alias=alias_clean,
                normalized_alias=normalize_catalog_text(alias_clean),
            )
        )
    return rec


def replace_canonical_episodes(
    session: Session,
    *,
    tvdb_id: int,
    episodes: List[dict[str, Any]],
) -> None:
    session.exec(
        CanonicalEpisode.__table__.delete().where(CanonicalEpisode.tvdb_id == tvdb_id)
    )
    for episode in episodes:
        title = str(episode.get("title") or "").strip()
        if not title:
            continue
        session.add(
            CanonicalEpisode(
                tvdb_id=tvdb_id,
                season=int(episode["season"]),
                episode=int(episode["episode"]),
                title=title,
                normalized_title=normalize_catalog_text(title),
                last_synced_at=utcnow(),
            )
        )


def is_catalog_bootstrap_ready(
    session: Session,
    *,
    providers: List[str],
) -> bool:
    if not providers:
        return True
    statuses = {
        row.provider: row
        for row in session.exec(
            select(ProviderIndexStatus).where(
                ProviderIndexStatus.provider.in_(providers)
            )
        ).all()
    }
    return all(
        status is not None
        and status.bootstrap_completed
        and bool(status.latest_success_generation)
        for status in (statuses.get(provider) for provider in providers)
    )


def catalog_title_count(session: Session, *, provider: Optional[str] = None) -> int:
    stmt = select(ProviderCatalogTitle)
    if provider:
        stmt = stmt.where(ProviderCatalogTitle.provider == provider)
    return len(session.exec(stmt).all())


def resolve_indexed_title(
    session: Session,
    *,
    provider: str,
    slug: str,
) -> Optional[str]:
    status = session.get(ProviderIndexStatus, provider)
    if status is None or not status.latest_success_generation:
        return None
    row = session.get(ProviderCatalogTitle, (provider, slug))
    if row is None or row.indexed_generation != status.latest_success_generation:
        return None
    return row.title if row else None


def search_indexed_provider_titles(
    session: Session,
    *,
    query: str,
    providers: List[str],
    media_type_hint: Optional[str] = None,
    limit: int = 20,
) -> List[ProviderCatalogTitle]:
    q_norm = normalize_catalog_text(query)
    if not q_norm:
        return []
    tokens = [token for token in q_norm.split(" ") if token]
    if not tokens:
        return []
    visible_generations = _visible_generation_map(session, providers=providers)
    if not visible_generations:
        return []
    stmt = select(ProviderCatalogTitle).where(
        ProviderCatalogTitle.provider.in_(providers)
    )
    if media_type_hint is not None:
        stmt = stmt.where(ProviderCatalogTitle.media_type_hint == media_type_hint)
    rows = [
        row
        for row in session.exec(stmt).all()
        if visible_generations.get(row.provider) == row.indexed_generation
    ]

    def _score(row: ProviderCatalogTitle) -> tuple[int, int]:
        names = [row.normalized_title]
        alias_rows = session.exec(
            select(ProviderCatalogAlias).where(
                (ProviderCatalogAlias.provider == row.provider)
                & (ProviderCatalogAlias.slug == row.slug)
            )
        ).all()
        names.extend(alias.normalized_alias for alias in alias_rows)
        best = 0
        exact = 0
        for name in names:
            name_tokens = set(token for token in name.split(" ") if token)
            overlap = len(name_tokens & set(tokens))
            if name == q_norm:
                exact = 1
            if overlap > best:
                best = overlap
        return (exact, best)

    ranked = sorted(
        rows,
        key=lambda row: _score(row),
        reverse=True,
    )
    filtered = [row for row in ranked if _score(row)[1] > 0 or _score(row)[0] > 0]
    return filtered[: max(1, limit)]


def list_indexed_titles_for_provider(
    session: Session,
    *,
    provider: str,
) -> List[ProviderCatalogTitle]:
    status = session.get(ProviderIndexStatus, provider)
    if status is None or not status.latest_success_generation:
        return []
    return list(
        session.exec(
            select(ProviderCatalogTitle).where(
                (ProviderCatalogTitle.provider == provider)
                & (
                    ProviderCatalogTitle.indexed_generation
                    == status.latest_success_generation
                )
            )
        ).all()
    )


def get_indexed_episode_languages(
    session: Session,
    *,
    provider: str,
    slug: str,
    season: int,
    episode: int,
) -> List[ProviderEpisodeLanguage]:
    status = session.get(ProviderIndexStatus, provider)
    if status is None or not status.latest_success_generation:
        return []
    return list(
        session.exec(
            select(ProviderEpisodeLanguage).where(
                (ProviderEpisodeLanguage.provider == provider)
                & (ProviderEpisodeLanguage.slug == slug)
                & (ProviderEpisodeLanguage.season == season)
                & (ProviderEpisodeLanguage.episode == episode)
                & (
                    ProviderEpisodeLanguage.indexed_generation
                    == status.latest_success_generation
                )
            )
        ).all()
    )


def list_indexed_provider_episodes(
    session: Session,
    *,
    provider: str,
    slug: str,
) -> List[ProviderCatalogEpisode]:
    status = session.get(ProviderIndexStatus, provider)
    if status is None or not status.latest_success_generation:
        return []
    return list(
        session.exec(
            select(ProviderCatalogEpisode).where(
                (ProviderCatalogEpisode.provider == provider)
                & (ProviderCatalogEpisode.slug == slug)
                & (
                    ProviderCatalogEpisode.indexed_generation
                    == status.latest_success_generation
                )
            )
        ).all()
    )


def list_indexed_episode_numbers_for_season(
    session: Session,
    *,
    provider: str,
    slug: str,
    season: int,
) -> List[int]:
    status = session.get(ProviderIndexStatus, provider)
    if status is None or not status.latest_success_generation:
        return []
    episodes = [
        int(row.episode)
        for row in session.exec(
            select(ProviderCatalogEpisode).where(
                (ProviderCatalogEpisode.provider == provider)
                & (ProviderCatalogEpisode.slug == slug)
                & (ProviderCatalogEpisode.season == season)
                & (
                    ProviderCatalogEpisode.indexed_generation
                    == status.latest_success_generation
                )
            )
        ).all()
    ]
    return sorted(set(episodes))


def find_canonical_series_by_ids_or_title(
    session: Session,
    *,
    tvdb_id: Optional[int] = None,
    tmdb_id: Optional[int] = None,
    imdb_id: Optional[str] = None,
    query: Optional[str] = None,
) -> Optional[CanonicalSeries]:
    if tvdb_id:
        row = session.get(CanonicalSeries, tvdb_id)
        if row is not None:
            return row
    if tmdb_id:
        row = session.exec(
            select(CanonicalSeries).where(CanonicalSeries.tmdb_id == tmdb_id)
        ).first()
        if row is not None:
            return row
    if imdb_id:
        row = session.exec(
            select(CanonicalSeries).where(CanonicalSeries.imdb_id == imdb_id)
        ).first()
        if row is not None:
            return row
    q_norm = normalize_catalog_text(query or "")
    if not q_norm:
        return None
    row = session.exec(
        select(CanonicalSeries).where(CanonicalSeries.normalized_title == q_norm)
    ).first()
    if row is not None:
        return row
    alias = session.exec(
        select(CanonicalSeriesAlias).where(
            CanonicalSeriesAlias.normalized_alias == q_norm
        )
    ).first()
    if alias is not None:
        return session.get(CanonicalSeries, alias.tvdb_id)
    return None


def find_provider_episode_mappings_for_canonical_episode(
    session: Session,
    *,
    tvdb_id: int,
    canonical_season: int,
    canonical_episode: int,
    providers: List[str],
) -> List[ProviderEpisodeMapping]:
    return list(
        session.exec(
            select(ProviderEpisodeMapping).where(
                (ProviderEpisodeMapping.tvdb_id == tvdb_id)
                & (ProviderEpisodeMapping.canonical_season == canonical_season)
                & (ProviderEpisodeMapping.canonical_episode == canonical_episode)
                & (ProviderEpisodeMapping.provider.in_(providers))
                & ProviderEpisodeMapping.confidence.in_(
                    ["confirmed", "high_confidence", "low_confidence"]
                )
            )
        ).all()
    )


def find_provider_episode_mappings_for_canonical_season(
    session: Session,
    *,
    tvdb_id: int,
    canonical_season: int,
    providers: List[str],
) -> List[ProviderEpisodeMapping]:
    return list(
        session.exec(
            select(ProviderEpisodeMapping).where(
                (ProviderEpisodeMapping.tvdb_id == tvdb_id)
                & (ProviderEpisodeMapping.canonical_season == canonical_season)
                & (ProviderEpisodeMapping.provider.in_(providers))
                & ProviderEpisodeMapping.confidence.in_(
                    ["confirmed", "high_confidence", "low_confidence"]
                )
            )
        ).all()
    )


def find_provider_episode_mapping(
    session: Session,
    *,
    provider: str,
    slug: str,
    provider_season: int,
    provider_episode: int,
) -> Optional[ProviderEpisodeMapping]:
    return session.exec(
        select(ProviderEpisodeMapping).where(
            (ProviderEpisodeMapping.provider == provider)
            & (ProviderEpisodeMapping.slug == slug)
            & (ProviderEpisodeMapping.provider_season == provider_season)
            & (ProviderEpisodeMapping.provider_episode == provider_episode)
            & ProviderEpisodeMapping.confidence.in_(
                ["confirmed", "high_confidence", "low_confidence"]
            )
        )
    ).first()


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
