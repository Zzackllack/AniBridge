from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import threading
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from loguru import logger
from sqlmodel import Session

from app.catalog.exceptions import CatalogNotReadyError
from app.catalog.providers import CatalogCrawlObserver, crawl_provider_catalog
from app.config import (
    ANIBRIDGE_TEST_MODE,
    CATALOG_SITES_LIST,
    CATALOG_SITE_CONFIGS,
    PROGRESS_STEP_PERCENT,
    PROVIDER_INDEX_GLOBAL_CONCURRENCY,
    PROVIDER_INDEX_SCHEDULER_POLL_SECONDS,
)
from app.db import (
    as_aware_utc,
    delete_provider_generation,
    engine,
    get_provider_index_status,
    is_catalog_bootstrap_ready,
    list_provider_index_statuses,
    prune_provider_generation,
    replace_canonical_episodes,
    replace_provider_catalog_aliases,
    replace_provider_catalog_episodes,
    replace_provider_catalog_title,
    replace_provider_episode_mappings,
    replace_provider_movie_mappings,
    replace_provider_series_mappings,
    upsert_canonical_series,
    upsert_provider_index_status,
    upsert_provider_title_index_state,
    utcnow,
)
from app.utils.terminal import ProgressReporter, ProgressSnapshot

_INDEXER: "ProviderCatalogIndexer | None" = None
_INDEXER_LOCK = threading.Lock()
_UNSET = object()
_DISCOVERY_HEARTBEAT_SECONDS = 15.0


@dataclass(slots=True)
class ProviderCatalogProgress:
    provider: str
    phase: str = "pending"
    processed_titles: int = 0
    total_titles: int | None = None
    current_slug: str = ""
    last_logged_step: int = -1

    @property
    def progress_percent(self) -> float | None:
        if not self.total_titles:
            return None
        if self.total_titles <= 0:
            return 100.0
        return round(
            max(0.0, min(100.0, self.processed_titles / self.total_titles * 100.0)),
            1,
        )


def get_catalog_indexer() -> "ProviderCatalogIndexer":
    global _INDEXER
    with _INDEXER_LOCK:
        if _INDEXER is None:
            _INDEXER = ProviderCatalogIndexer()
        return _INDEXER


def get_catalog_readiness_error() -> str | None:
    indexer = get_catalog_indexer()
    with Session(engine) as session:
        statuses = list_provider_index_statuses(session)
        if ANIBRIDGE_TEST_MODE and not statuses:
            return None
        if is_catalog_bootstrap_ready(session, providers=CATALOG_SITES_LIST):
            return None
        pending: list[str] = []
        snapshot = indexer.get_progress_snapshot()
        by_provider = {item["provider"]: item for item in snapshot.get("providers", [])}
        for provider in CATALOG_SITES_LIST:
            status = get_provider_index_status(session, provider=provider)
            if status is None or not status.bootstrap_completed:
                progress = by_provider.get(provider, {})
                processed = progress.get("processed_titles")
                total = progress.get("total_titles")
                percent = progress.get("progress_percent")
                phase = progress.get("phase") or "pending"
                if isinstance(processed, int) and isinstance(total, int) and total > 0:
                    pending.append(
                        f"{provider} ({processed}/{total}, {percent:.1f}%, {phase})"
                    )
                else:
                    pending.append(f"{provider} ({phase})")
        if not pending:
            return None
        return (
            "Provider catalog bootstrap is still running. "
            f"Pending providers: {', '.join(pending)}."
        )


def require_catalog_ready() -> None:
    message = get_catalog_readiness_error()
    if message:
        logger.warning("Catalog-dependent request blocked: {}", message)
        raise CatalogNotReadyError(message)


class ProviderCatalogIndexer:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._active = threading.Semaphore(PROVIDER_INDEX_GLOBAL_CONCURRENCY)
        self._progress_lock = threading.Lock()
        self._progress: dict[str, ProviderCatalogProgress] = {}
        self._workers_lock = threading.Lock()
        self._workers: dict[str, threading.Thread] = {}

    def start(self) -> None:
        self._ensure_status_rows()
        self._log_bootstrap_state()
        if ANIBRIDGE_TEST_MODE:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        logger.info(
            "Provider catalog scheduler starting: poll={}s global_concurrency={} providers={}",
            PROVIDER_INDEX_SCHEDULER_POLL_SECONDS,
            PROVIDER_INDEX_GLOBAL_CONCURRENCY,
            ", ".join(CATALOG_SITES_LIST),
        )
        self._thread = threading.Thread(
            target=self._run_loop,
            name="provider-catalog-indexer",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        with self._workers_lock:
            workers = list(self._workers.values())
        for worker in workers:
            worker.join(timeout=5)

    def run_due_once(self) -> None:
        with Session(engine) as session:
            statuses = list_provider_index_statuses(session)
        if not statuses:
            logger.warning("Provider catalog scheduler: no provider status rows found")
            return
        logger.debug(
            "Provider catalog scheduler pass: bootstrap_ready={} providers={}",
            self._is_bootstrap_ready(),
            ", ".join(
                f"{status.provider}={status.status}"
                for status in sorted(statuses, key=lambda item: item.provider)
            ),
        )
        for status in statuses:
            if self._is_due(status):
                logger.info(
                    "Provider catalog scheduler: {} is due (status={} bootstrap_completed={} next_refresh_after={} latest_success_at={})",
                    status.provider,
                    status.status,
                    status.bootstrap_completed,
                    status.next_refresh_after.isoformat()
                    if status.next_refresh_after is not None
                    else None,
                    status.latest_success_at.isoformat()
                    if status.latest_success_at is not None
                    else None,
                )
                self.refresh_provider(status.provider)
            else:
                logger.debug(
                    "Provider catalog scheduler: {} not due (status={} bootstrap_completed={} next_refresh_after={} latest_success_at={})",
                    status.provider,
                    status.status,
                    status.bootstrap_completed,
                    status.next_refresh_after.isoformat()
                    if status.next_refresh_after is not None
                    else None,
                    status.latest_success_at.isoformat()
                    if status.latest_success_at is not None
                    else None,
                )

    def refresh_provider(self, provider: str) -> None:
        with self._workers_lock:
            existing = self._workers.get(provider)
            if existing is not None and existing.is_alive():
                logger.debug(
                    "Provider catalog scheduler: {} already running in worker {}",
                    provider,
                    existing.name,
                )
                return
        if not self._active.acquire(blocking=False):
            logger.warning(
                "Provider catalog scheduler: concurrency exhausted, skipping {} for now",
                provider,
            )
            return
        logger.info("Provider catalog scheduler: starting refresh for {}", provider)
        worker = threading.Thread(
            target=self._run_provider_refresh,
            name=f"provider-index-{provider}",
            args=(provider,),
            daemon=True,
        )
        with self._workers_lock:
            self._workers[provider] = worker
        worker.start()

    def get_progress_snapshot(self) -> dict[str, object]:
        with Session(engine) as session:
            statuses = {
                status.provider: status
                for status in list_provider_index_statuses(session)
            }
            bootstrap_ready = is_catalog_bootstrap_ready(
                session, providers=CATALOG_SITES_LIST
            )
        with self._progress_lock:
            runtime = {
                provider: ProviderCatalogProgress(
                    provider=snapshot.provider,
                    phase=snapshot.phase,
                    processed_titles=snapshot.processed_titles,
                    total_titles=snapshot.total_titles,
                    current_slug=snapshot.current_slug,
                    last_logged_step=snapshot.last_logged_step,
                )
                for provider, snapshot in self._progress.items()
            }
        providers: list[dict[str, object]] = []
        for provider in CATALOG_SITES_LIST:
            status = statuses.get(provider)
            progress = runtime.get(provider, ProviderCatalogProgress(provider=provider))
            phase = progress.phase
            if phase == "pending" and status is not None:
                phase = status.status
            providers.append(
                {
                    "provider": provider,
                    "status": status.status if status is not None else "pending",
                    "bootstrap_completed": (
                        bool(status.bootstrap_completed)
                        if status is not None
                        else False
                    ),
                    "phase": phase,
                    "processed_titles": progress.processed_titles,
                    "total_titles": progress.total_titles,
                    "progress_percent": progress.progress_percent,
                    "current_slug": progress.current_slug or None,
                    "last_error_summary": (
                        status.last_error_summary if status is not None else ""
                    ),
                    "latest_started_at": (
                        status.latest_started_at.isoformat()
                        if status is not None and status.latest_started_at is not None
                        else None
                    ),
                    "latest_completed_at": (
                        status.latest_completed_at.isoformat()
                        if status is not None and status.latest_completed_at is not None
                        else None
                    ),
                }
            )
        return {
            "bootstrap_ready": bootstrap_ready,
            "bootstrapping": not bootstrap_ready,
            "providers": providers,
        }

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_due_once()
            except Exception as exc:
                logger.exception("Provider catalog scheduler loop failed: {}", exc)
            if self._stop_event.wait(PROVIDER_INDEX_SCHEDULER_POLL_SECONDS):
                break

    def _run_provider_refresh(self, provider: str) -> None:
        try:
            self._refresh_provider(provider)
        finally:
            self._active.release()
            with self._workers_lock:
                self._workers.pop(provider, None)

    def _ensure_status_rows(self) -> None:
        with Session(engine) as session:
            now = None
            for provider in CATALOG_SITES_LIST:
                self._set_progress(provider, phase="pending")
                hours = float(
                    CATALOG_SITE_CONFIGS.get(provider, {}).get(
                        "provider_index_refresh_hours", 24.0
                    )
                )
                status = get_provider_index_status(session, provider=provider)
                if status is None:
                    logger.warning(
                        "Provider catalog bootstrap: no persisted index state for {}. Initial bootstrap required.",
                        provider,
                    )
                    upsert_provider_index_status(
                        session,
                        provider=provider,
                        refresh_interval_hours=hours,
                        status="pending",
                        bootstrap_completed=False,
                        next_refresh_after=now,
                    )
                    continue
                if status.status == "running":
                    logger.warning(
                        "Provider catalog bootstrap: recovered interrupted run for {} started_at={} cursor_slug={}. Marking it pending for retry.",
                        provider,
                        status.latest_started_at.isoformat()
                        if status.latest_started_at is not None
                        else None,
                        status.cursor_title_slug or None,
                    )
                    upsert_provider_index_status(
                        session,
                        provider=provider,
                        refresh_interval_hours=hours,
                        status="pending",
                        latest_completed_at=utcnow(),
                        next_refresh_after=now,
                        failure_count=status.failure_count + 1,
                        last_error_summary="Interrupted by process restart before completion.",
                    )
                else:
                    logger.debug(
                        "Provider catalog bootstrap: loaded persisted state for {} status={} bootstrap_completed={} latest_success_generation={} next_refresh_after={}",
                        provider,
                        status.status,
                        status.bootstrap_completed,
                        status.latest_success_generation,
                        status.next_refresh_after.isoformat()
                        if status.next_refresh_after is not None
                        else None,
                    )

    def _is_due(self, status) -> bool:
        if status.status == "running":
            return False
        if status.latest_success_at is None:
            return True
        if status.next_refresh_after is None:
            return True
        return as_aware_utc(status.next_refresh_after) <= utcnow()

    def _refresh_provider(self, provider: str) -> None:
        refresh_interval_hours = float(
            CATALOG_SITE_CONFIGS.get(provider, {}).get(
                "provider_index_refresh_hours", 24.0
            )
        )
        generation = uuid4().hex
        reporter: ProgressReporter | None = None
        self._set_progress(
            provider,
            phase="discovering_titles",
            processed_titles=0,
            total_titles=None,
            current_slug="",
            reset_log_step=True,
        )
        logger.info("Provider catalog {}: discovering titles", provider)
        with Session(engine) as session:
            current = get_provider_index_status(session, provider=provider)
            failure_count = 0 if current is None else current.failure_count
            _ = failure_count
            upsert_provider_index_status(
                session,
                provider=provider,
                refresh_interval_hours=refresh_interval_hours,
                status="running",
                current_generation=generation,
                latest_started_at=utcnow(),
            )

        try:
            titles = self._crawl_provider_catalog_with_heartbeat(provider)
            logger.info(
                "Provider catalog {}: discovered {} titles",
                provider,
                len(titles),
            )
            reporter = ProgressReporter(
                label=f"Catalog {provider}",
                unit="title",
                unit_scale=False,
            )
            reporter.update(
                ProgressSnapshot(
                    downloaded=0,
                    total=len(titles),
                    status="persisting_titles",
                )
            )
            self._set_progress(
                provider,
                phase="persisting_titles",
                total_titles=len(titles),
                processed_titles=0,
                current_slug="",
                reset_log_step=True,
            )
            for title_record in titles:
                with Session(engine) as session:
                    upsert_provider_index_status(
                        session,
                        provider=provider,
                        refresh_interval_hours=refresh_interval_hours,
                        cursor_title_slug=title_record.slug,
                    )
                    upsert_provider_title_index_state(
                        session,
                        provider=provider,
                        slug=title_record.slug,
                        attempted_at=utcnow(),
                    )
                    replace_provider_catalog_title(
                        session,
                        provider=provider,
                        slug=title_record.slug,
                        title=title_record.title,
                        media_type_hint=title_record.media_type_hint,
                        relative_path=title_record.relative_path,
                        indexed_generation=generation,
                    )
                    replace_provider_catalog_aliases(
                        session,
                        provider=provider,
                        slug=title_record.slug,
                        aliases=title_record.aliases,
                        indexed_generation=generation,
                    )
                    replace_provider_catalog_episodes(
                        session,
                        provider=provider,
                        slug=title_record.slug,
                        episodes=[
                            {
                                "season": episode.season,
                                "episode": episode.episode,
                                "relative_path": episode.relative_path,
                                "title_primary": episode.title_primary,
                                "title_secondary": episode.title_secondary,
                                "media_type_hint": episode.media_type_hint,
                                "languages": [
                                    {
                                        "language": lang.language,
                                        "host_hints": lang.host_hints,
                                    }
                                    for lang in episode.languages
                                ],
                            }
                            for episode in title_record.episodes
                        ],
                        indexed_generation=generation,
                    )
                    if title_record.canonical.series is not None:
                        series = title_record.canonical.series
                        upsert_canonical_series(
                            session,
                            tvdb_id=int(series["tvdb_id"]),
                            title=str(series["title"]),
                            tmdb_id=series.get("tmdb_id"),
                            imdb_id=series.get("imdb_id"),
                            tvmaze_id=series.get("tvmaze_id"),
                            anilist_id=series.get("anilist_id"),
                            mal_id=series.get("mal_id"),
                            aliases=list(series.get("aliases") or []),
                        )
                        replace_canonical_episodes(
                            session,
                            tvdb_id=int(series["tvdb_id"]),
                            episodes=title_record.canonical.episodes,
                        )
                    replace_provider_series_mappings(
                        session,
                        provider=provider,
                        slug=title_record.slug,
                        mappings=title_record.canonical.series_mappings,
                    )
                    replace_provider_episode_mappings(
                        session,
                        provider=provider,
                        slug=title_record.slug,
                        mappings=title_record.canonical.episode_mappings,
                    )
                    replace_provider_movie_mappings(
                        session,
                        provider=provider,
                        slug=title_record.slug,
                        mappings=title_record.canonical.movie_mappings,
                    )
                    upsert_provider_title_index_state(
                        session,
                        provider=provider,
                        slug=title_record.slug,
                        succeeded_at=utcnow(),
                        failure_count=0,
                        last_error_summary="",
                    )
                    session.commit()
                self._advance_progress(provider, current_slug=title_record.slug)
                processed_titles = self._get_processed_titles(provider)
                reporter.update(
                    ProgressSnapshot(
                        downloaded=min(len(titles), processed_titles),
                        total=len(titles),
                        status="persisting_titles",
                    )
                )
            completed_at = utcnow()
            with Session(engine) as session:
                prune_provider_generation(
                    session,
                    provider=provider,
                    keep_generation=generation,
                )
                upsert_provider_index_status(
                    session,
                    provider=provider,
                    refresh_interval_hours=refresh_interval_hours,
                    status="ready",
                    current_generation=generation,
                    latest_success_generation=generation,
                    latest_completed_at=completed_at,
                    latest_success_at=completed_at,
                    next_refresh_after=completed_at
                    + timedelta(hours=refresh_interval_hours),
                    bootstrap_completed=True,
                    failure_count=0,
                    last_error_summary="",
                    cursor_title_slug="",
                )
            self._set_progress(
                provider,
                phase="ready",
                current_slug="",
            )
            if reporter is not None:
                reporter.close()
        except Exception as exc:
            logger.exception(
                "Provider catalog refresh failed for {}: {}", provider, exc
            )
            if reporter is not None:
                reporter.close()
            completed_at = utcnow()
            with Session(engine) as session:
                delete_provider_generation(
                    session,
                    provider=provider,
                    generation=generation,
                )
                current = get_provider_index_status(session, provider=provider)
                failure_count = 1 if current is None else current.failure_count + 1
                upsert_provider_index_status(
                    session,
                    provider=provider,
                    refresh_interval_hours=refresh_interval_hours,
                    status="failed",
                    latest_completed_at=completed_at,
                    next_refresh_after=completed_at
                    + timedelta(hours=refresh_interval_hours),
                    failure_count=failure_count,
                    last_error_summary=str(exc)[:500],
                )
            self._set_progress(
                provider,
                phase="failed",
                current_slug="",
            )

    def _crawl_provider_catalog_with_heartbeat(self, provider: str) -> list[object]:
        elapsed_seconds = 0.0
        observer = CatalogCrawlObserver(
            on_index_loaded=lambda total: self._on_title_index_loaded(provider, total),
            on_title_started=lambda slug: self._on_title_started(provider, slug),
            on_title_crawled=lambda slug: self._on_title_crawled(provider, slug),
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                crawl_provider_catalog,
                provider,
                observer=observer,
            )
            while True:
                try:
                    return future.result(timeout=_DISCOVERY_HEARTBEAT_SECONDS)
                except FutureTimeoutError:
                    elapsed_seconds += _DISCOVERY_HEARTBEAT_SECONDS
                    processed = self._get_processed_titles(provider)
                    total = self._get_total_titles(provider)
                    current_slug = self._get_current_slug(provider)
                    if total is not None:
                        percent = 100.0 if total <= 0 else round(processed / total * 100.0, 1)
                        logger.info(
                            "Provider catalog {}: crawling title details {}/{} ({}%) after {}s current={}",
                            provider,
                            processed,
                            total,
                            percent,
                            int(elapsed_seconds),
                            current_slug or "-",
                        )
                    else:
                        logger.info(
                            "Provider catalog {}: still discovering titles after {}s current={}",
                            provider,
                            int(elapsed_seconds),
                            current_slug or "-",
                        )

    def _on_title_index_loaded(self, provider: str, total_titles: int) -> None:
        self._set_progress(
            provider,
            phase="crawling_titles",
            total_titles=total_titles,
            processed_titles=0,
            current_slug="",
            reset_log_step=True,
        )
        logger.info(
            "Provider catalog {}: loaded title index with {} titles",
            provider,
            total_titles,
        )

    def _on_title_started(self, provider: str, slug: str) -> None:
        self._set_progress(
            provider,
            phase="crawling_titles",
            current_slug=slug,
        )

    def _on_title_crawled(self, provider: str, slug: str) -> None:
        self._advance_progress(provider, current_slug=slug)

    def _is_bootstrap_ready(self) -> bool:
        with Session(engine) as session:
            return is_catalog_bootstrap_ready(session, providers=CATALOG_SITES_LIST)

    def _log_bootstrap_state(self) -> None:
        with Session(engine) as session:
            statuses = list_provider_index_statuses(session)
            bootstrap_ready = is_catalog_bootstrap_ready(
                session, providers=CATALOG_SITES_LIST
            )
        if not statuses:
            logger.warning(
                "Provider catalog bootstrap: no provider status rows exist yet"
            )
            return
        if bootstrap_ready:
            logger.info("Provider catalog bootstrap: already complete")
        else:
            logger.warning(
                "Provider catalog bootstrap: incomplete, requests may be gated"
            )
        for status in sorted(statuses, key=lambda item: item.provider):
            logger.info(
                "Provider catalog bootstrap state: provider={} status={} bootstrap_completed={} latest_success_generation={} latest_started_at={} latest_completed_at={} next_refresh_after={} cursor_slug={} last_error={}",
                status.provider,
                status.status,
                status.bootstrap_completed,
                status.latest_success_generation,
                status.latest_started_at.isoformat()
                if status.latest_started_at is not None
                else None,
                status.latest_completed_at.isoformat()
                if status.latest_completed_at is not None
                else None,
                status.next_refresh_after.isoformat()
                if status.next_refresh_after is not None
                else None,
                status.cursor_title_slug or None,
                status.last_error_summary or None,
            )

    def _set_progress(
        self,
        provider: str,
        *,
        phase: str | None = None,
        processed_titles: int | None = None,
        total_titles: int | None | object = _UNSET,
        current_slug: str | None = None,
        reset_log_step: bool = False,
    ) -> None:
        with self._progress_lock:
            snapshot = self._progress.get(provider)
            if snapshot is None:
                snapshot = ProviderCatalogProgress(provider=provider)
                self._progress[provider] = snapshot
            if phase is not None:
                snapshot.phase = phase
            if processed_titles is not None:
                snapshot.processed_titles = processed_titles
            if total_titles is not _UNSET:
                snapshot.total_titles = total_titles
            if current_slug is not None:
                snapshot.current_slug = current_slug
            if reset_log_step:
                snapshot.last_logged_step = -1

    def _advance_progress(self, provider: str, *, current_slug: str) -> None:
        with self._progress_lock:
            snapshot = self._progress.get(provider)
            if snapshot is None:
                snapshot = ProviderCatalogProgress(provider=provider)
                self._progress[provider] = snapshot
            snapshot.processed_titles += 1
            snapshot.current_slug = current_slug
            total = snapshot.total_titles
            percent = snapshot.progress_percent
            if total is None or percent is None:
                return
            step = max(1, int(PROGRESS_STEP_PERCENT))
            current_step = int(percent) // step
            if percent < 100.0 and current_step <= snapshot.last_logged_step:
                return
            snapshot.last_logged_step = current_step
            logger.info(
                "Provider catalog {} progress [{}]: {}/{} ({}%) current={}",
                provider,
                snapshot.phase,
                snapshot.processed_titles,
                total,
                percent,
                current_slug,
            )

    def _get_processed_titles(self, provider: str) -> int:
        with self._progress_lock:
            snapshot = self._progress.get(provider)
            if snapshot is None:
                return 0
            return snapshot.processed_titles

    def _get_total_titles(self, provider: str) -> int | None:
        with self._progress_lock:
            snapshot = self._progress.get(provider)
            if snapshot is None:
                return None
            return snapshot.total_titles

    def _get_current_slug(self, provider: str) -> str:
        with self._progress_lock:
            snapshot = self._progress.get(provider)
            if snapshot is None:
                return ""
            return snapshot.current_slug
