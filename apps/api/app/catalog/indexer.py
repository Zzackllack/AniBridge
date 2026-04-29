from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from queue import Empty, Full, Queue
from threading import Event, Lock, Semaphore, Thread
from time import monotonic
from uuid import uuid4

from loguru import logger
from sqlmodel import Session

from app.catalog.exceptions import CatalogNotReadyError
from app.catalog.providers import (
    CatalogCrawlObserver,
    TitleRecord,
    stream_provider_catalog,
)
from app.config import (
    ANIBRIDGE_TEST_MODE,
    CATALOG_SITES_LIST,
    CATALOG_SITE_CONFIGS,
    PROGRESS_STEP_PERCENT,
    PROVIDER_INDEX_BACKPRESSURE_LOG_SECONDS,
    PROVIDER_INDEX_FAILURE_THRESHOLD_PERCENT,
    PROVIDER_INDEX_GLOBAL_CONCURRENCY,
    PROVIDER_INDEX_QUEUE_SIZE,
    PROVIDER_INDEX_SCHEDULER_POLL_SECONDS,
    PROVIDER_INDEX_WRITER_BATCH_SIZE,
    PROVIDER_INDEX_WRITER_FLUSH_SECONDS,
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
_INDEXER_LOCK = Lock()
_UNSET = object()
_QUEUE_SENTINEL = object()


@dataclass(slots=True)
class ProviderCatalogProgress:
    provider: str
    phase: str = "pending"
    crawled_titles: int = 0
    persisted_titles: int = 0
    failed_titles: int = 0
    total_titles: int | None = None
    current_slug: str = ""
    queue_depth: int = 0
    last_logged_crawl_step: int = -1
    last_logged_persist_step: int = -1

    @property
    def processed_titles(self) -> int:
        return self.persisted_titles

    @property
    def writer_lag_titles(self) -> int:
        return max(0, self.crawled_titles - self.persisted_titles)

    @property
    def progress_percent(self) -> float | None:
        if not self.total_titles:
            return None
        if self.total_titles <= 0:
            return 100.0
        return round(
            max(0.0, min(100.0, self.persisted_titles / self.total_titles * 100.0)),
            1,
        )

    @property
    def crawl_percent(self) -> float | None:
        if not self.total_titles:
            return None
        if self.total_titles <= 0:
            return 100.0
        completed = self.crawled_titles + self.failed_titles
        return round(max(0.0, min(100.0, completed / self.total_titles * 100.0)), 1)


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
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._active = Semaphore(PROVIDER_INDEX_GLOBAL_CONCURRENCY)
        self._progress_lock = Lock()
        self._progress: dict[str, ProviderCatalogProgress] = {}
        self._workers_lock = Lock()
        self._workers: dict[str, Thread] = {}

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
        self._thread = Thread(
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
        worker = Thread(
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
                    crawled_titles=snapshot.crawled_titles,
                    persisted_titles=snapshot.persisted_titles,
                    failed_titles=snapshot.failed_titles,
                    total_titles=snapshot.total_titles,
                    current_slug=snapshot.current_slug,
                    queue_depth=snapshot.queue_depth,
                    last_logged_crawl_step=snapshot.last_logged_crawl_step,
                    last_logged_persist_step=snapshot.last_logged_persist_step,
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
            latest_success_generation = (
                status.latest_success_generation if status is not None else None
            )
            current_generation = (
                status.current_generation if status is not None else None
            )
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
                    "crawled_titles": progress.crawled_titles,
                    "persisted_titles": progress.persisted_titles,
                    "failed_titles": progress.failed_titles,
                    "total_titles": progress.total_titles,
                    "progress_percent": progress.progress_percent,
                    "crawl_progress_percent": progress.crawl_percent,
                    "queue_depth": progress.queue_depth,
                    "writer_lag_titles": progress.writer_lag_titles,
                    "current_slug": progress.current_slug or None,
                    "serving_previous_generation": bool(
                        status is not None
                        and status.status == "running"
                        and latest_success_generation
                        and current_generation
                        and current_generation != latest_success_generation
                    ),
                    "latest_success_generation": latest_success_generation,
                    "staging_generation": (
                        current_generation
                        if current_generation != latest_success_generation
                        else None
                    ),
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
                        next_refresh_after=None,
                    )
                    continue
                stale_generation = self._stale_generation(status)
                if stale_generation is not None:
                    logger.warning(
                        "Provider catalog bootstrap: found interrupted staging generation for {} generation={} status={} cursor_slug={}. Cleaning it up before retry.",
                        provider,
                        stale_generation,
                        status.status,
                        status.cursor_title_slug or None,
                    )
                    delete_provider_generation(
                        session,
                        provider=provider,
                        generation=stale_generation,
                    )
                    upsert_provider_index_status(
                        session,
                        provider=provider,
                        refresh_interval_hours=hours,
                        status="pending",
                        current_generation=None,
                        latest_completed_at=utcnow(),
                        next_refresh_after=None,
                        failure_count=status.failure_count + 1,
                        last_error_summary="Interrupted staging generation cleaned up after restart.",
                    )
                    continue
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
        queue: Queue[TitleRecord | object] = Queue(maxsize=PROVIDER_INDEX_QUEUE_SIZE)
        writer_failure: list[BaseException] = []
        state_lock = Lock()
        failed_titles = 0
        completed_titles = 0
        self._set_progress(
            provider,
            phase="discovering_titles",
            crawled_titles=0,
            persisted_titles=0,
            failed_titles=0,
            total_titles=None,
            current_slug="",
            queue_depth=0,
            reset_log_steps=True,
        )
        logger.info("Provider catalog {}: discovering titles", provider)

        with Session(engine) as session:
            current = get_provider_index_status(session, provider=provider)
            if current is not None:
                stale_generation = self._stale_generation(current)
                if stale_generation is not None:
                    delete_provider_generation(
                        session,
                        provider=provider,
                        generation=stale_generation,
                    )
            upsert_provider_index_status(
                session,
                provider=provider,
                refresh_interval_hours=refresh_interval_hours,
                status="running",
                current_generation=generation,
                latest_started_at=utcnow(),
                latest_completed_at=None,
                next_refresh_after=None,
                last_error_summary="",
                cursor_title_slug="",
            )

        reporter = ProgressReporter(
            label=f"Catalog {provider}",
            unit="title",
            unit_scale=False,
        )
        reporter.update(
            ProgressSnapshot(
                downloaded=0,
                total=None,
                status="discovering_titles",
            )
        )

        writer = Thread(
            target=self._writer_loop,
            name=f"provider-index-writer-{provider}",
            args=(
                provider,
                generation,
                refresh_interval_hours,
                queue,
                reporter,
                writer_failure,
            ),
            daemon=True,
        )
        writer.start()

        def emit_title(record: TitleRecord) -> None:
            last_backpressure_log = 0.0
            while True:
                if writer_failure:
                    raise RuntimeError(
                        f"writer failed for {provider}: {writer_failure[0]}"
                    )
                try:
                    queue.put(record, timeout=1.0)
                except Full:
                    depth = queue.qsize()
                    self._set_progress(provider, queue_depth=depth)
                    now = monotonic()
                    if (
                        now - last_backpressure_log
                        >= PROVIDER_INDEX_BACKPRESSURE_LOG_SECONDS
                    ):
                        logger.warning(
                            "Provider catalog {}: writer backpressure queue_depth={} lag_titles={}",
                            provider,
                            depth,
                            self._get_writer_lag(provider),
                        )
                        last_backpressure_log = now
                    continue
                self._set_progress(provider, queue_depth=queue.qsize())
                return

        def on_index_loaded(total_titles: int) -> None:
            self._set_progress(
                provider,
                phase="crawling_titles",
                total_titles=total_titles,
                current_slug="",
                queue_depth=queue.qsize(),
                reset_log_steps=True,
            )
            logger.info(
                "Provider catalog {}: loaded title index with {} titles",
                provider,
                total_titles,
            )
            reporter.update(
                ProgressSnapshot(
                    downloaded=0,
                    total=total_titles,
                    status="crawling_titles",
                )
            )

        def on_title_started(slug: str) -> None:
            self._set_progress(provider, phase="crawling_titles", current_slug=slug)

        def on_title_crawled(slug: str) -> None:
            nonlocal completed_titles
            with state_lock:
                completed_titles += 1
            self._advance_crawl_progress(
                provider,
                current_slug=slug,
                queue_depth=queue.qsize(),
            )

        def on_title_failed(slug: str, reason: str) -> None:
            nonlocal completed_titles, failed_titles
            with state_lock:
                completed_titles += 1
                failed_titles += 1
                failure_count = failed_titles
            self._record_title_failure(provider, slug, reason)
            self._advance_failed_progress(
                provider,
                current_slug=slug,
                queue_depth=queue.qsize(),
            )
            total_titles = self._get_total_titles(provider)
            if total_titles and total_titles > 0:
                failure_rate = failure_count / total_titles * 100.0
                if failure_rate > PROVIDER_INDEX_FAILURE_THRESHOLD_PERCENT:
                    raise RuntimeError(
                        "provider refresh failure threshold exceeded: "
                        f"{failure_count}/{total_titles} titles failed "
                        f"({failure_rate:.1f}% > {PROVIDER_INDEX_FAILURE_THRESHOLD_PERCENT:.1f}%)"
                    )

        observer = CatalogCrawlObserver(
            on_index_loaded=on_index_loaded,
            on_title_started=on_title_started,
            on_title_crawled=on_title_crawled,
            on_title_failed=on_title_failed,
        )

        try:
            summary = stream_provider_catalog(
                provider,
                emit_title=emit_title,
                observer=observer,
            )
            if writer_failure:
                raise RuntimeError(f"writer failed for {provider}: {writer_failure[0]}")
            if summary.discovered_titles == 0:
                logger.warning("Provider catalog {}: discovered zero titles", provider)
        except Exception as exc:
            logger.exception(
                "Provider catalog refresh failed for {}: {}", provider, exc
            )
            queue.put(_QUEUE_SENTINEL)
            writer.join(timeout=30)
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
                    current_generation=None,
                    latest_completed_at=completed_at,
                    next_refresh_after=completed_at
                    + timedelta(hours=refresh_interval_hours),
                    failure_count=failure_count,
                    last_error_summary=str(exc)[:500],
                )
            self._set_progress(
                provider,
                phase="failed",
                queue_depth=0,
                current_slug="",
            )
            return

        queue.put(_QUEUE_SENTINEL)
        writer.join()
        if writer_failure:
            exc = RuntimeError(f"writer failed for {provider}: {writer_failure[0]}")
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
                    current_generation=None,
                    latest_completed_at=completed_at,
                    next_refresh_after=completed_at
                    + timedelta(hours=refresh_interval_hours),
                    failure_count=failure_count,
                    last_error_summary=str(exc)[:500],
                )
            self._set_progress(
                provider,
                phase="failed",
                queue_depth=0,
                current_slug="",
            )
            return

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
            queue_depth=0,
            current_slug="",
        )
        logger.info(
            "Provider catalog {}: promoted staging generation {} persisted={}/{} failed={}",
            provider,
            generation,
            self._get_persisted_titles(provider),
            self._get_total_titles(provider) or 0,
            self._get_failed_titles(provider),
        )
        if reporter is not None:
            reporter.close()

    def _writer_loop(
        self,
        provider: str,
        generation: str,
        refresh_interval_hours: float,
        queue: Queue[TitleRecord | object],
        reporter: ProgressReporter | None,
        writer_failure: list[BaseException],
    ) -> None:
        batch: list[TitleRecord] = []
        last_flush_at = monotonic()
        try:
            while True:
                timeout = max(
                    0.1,
                    PROVIDER_INDEX_WRITER_FLUSH_SECONDS - (monotonic() - last_flush_at),
                )
                try:
                    item = queue.get(timeout=timeout)
                except Empty:
                    item = None
                if item is None:
                    if batch:
                        self._flush_writer_batch(
                            provider,
                            generation,
                            refresh_interval_hours,
                            batch,
                            queue_depth=queue.qsize(),
                            reporter=reporter,
                        )
                        batch = []
                        last_flush_at = monotonic()
                    continue
                if item is _QUEUE_SENTINEL:
                    if batch:
                        self._flush_writer_batch(
                            provider,
                            generation,
                            refresh_interval_hours,
                            batch,
                            queue_depth=queue.qsize(),
                            reporter=reporter,
                        )
                    return
                batch.append(item)
                if len(batch) >= PROVIDER_INDEX_WRITER_BATCH_SIZE:
                    self._flush_writer_batch(
                        provider,
                        generation,
                        refresh_interval_hours,
                        batch,
                        queue_depth=queue.qsize(),
                        reporter=reporter,
                    )
                    batch = []
                    last_flush_at = monotonic()
        except BaseException as exc:
            writer_failure.append(exc)
            logger.exception("Provider catalog writer failed for {}: {}", provider, exc)

    def _flush_writer_batch(
        self,
        provider: str,
        generation: str,
        refresh_interval_hours: float,
        batch: list[TitleRecord],
        *,
        queue_depth: int,
        reporter: ProgressReporter | None,
    ) -> None:
        if not batch:
            return
        last_slug = batch[-1].slug
        with Session(engine) as session:
            for record in batch:
                now = utcnow()
                upsert_provider_title_index_state(
                    session,
                    provider=provider,
                    slug=record.slug,
                    attempted_at=now,
                    commit=False,
                )
                self._persist_title_record(
                    session,
                    record=record,
                    indexed_generation=generation,
                )
                upsert_provider_title_index_state(
                    session,
                    provider=provider,
                    slug=record.slug,
                    succeeded_at=now,
                    failure_count=0,
                    last_error_summary="",
                    commit=False,
                )
            upsert_provider_index_status(
                session,
                provider=provider,
                refresh_interval_hours=refresh_interval_hours,
                status="running",
                current_generation=generation,
                cursor_title_slug=last_slug,
                last_error_summary="",
                commit=False,
            )
            session.commit()
        self._advance_persist_progress(
            provider,
            current_slug=last_slug,
            count=len(batch),
            queue_depth=queue_depth,
        )
        persisted = self._get_persisted_titles(provider)
        total_titles = self._get_total_titles(provider)
        if reporter is not None:
            reporter.update(
                ProgressSnapshot(
                    downloaded=persisted,
                    total=total_titles,
                    status="persisting_titles",
                )
            )
        logger.info(
            "Provider catalog {}: persisted batch size={} persisted={}/{} queue_depth={} writer_lag={}",
            provider,
            len(batch),
            persisted,
            total_titles or 0,
            queue_depth,
            self._get_writer_lag(provider),
        )

    def _persist_title_record(
        self,
        session: Session,
        *,
        record: TitleRecord,
        indexed_generation: str,
    ) -> None:
        replace_provider_catalog_title(
            session,
            provider=record.provider,
            slug=record.slug,
            title=record.title,
            media_type_hint=record.media_type_hint,
            relative_path=record.relative_path,
            indexed_generation=indexed_generation,
        )
        replace_provider_catalog_aliases(
            session,
            provider=record.provider,
            slug=record.slug,
            aliases=record.aliases,
            indexed_generation=indexed_generation,
        )
        replace_provider_catalog_episodes(
            session,
            provider=record.provider,
            slug=record.slug,
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
                            "language": language.language,
                            "host_hints": language.host_hints,
                        }
                        for language in episode.languages
                    ],
                }
                for episode in record.episodes
            ],
            indexed_generation=indexed_generation,
        )
        if record.canonical.series is not None:
            series = record.canonical.series
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
                episodes=record.canonical.episodes,
            )
        replace_provider_series_mappings(
            session,
            provider=record.provider,
            slug=record.slug,
            mappings=record.canonical.series_mappings,
            indexed_generation=indexed_generation,
        )
        replace_provider_episode_mappings(
            session,
            provider=record.provider,
            slug=record.slug,
            mappings=record.canonical.episode_mappings,
            indexed_generation=indexed_generation,
        )
        replace_provider_movie_mappings(
            session,
            provider=record.provider,
            slug=record.slug,
            mappings=record.canonical.movie_mappings,
            indexed_generation=indexed_generation,
        )

    def _record_title_failure(self, provider: str, slug: str, reason: str) -> None:
        with Session(engine) as session:
            current = get_provider_index_status(session, provider=provider)
            refresh_interval_hours = float(
                CATALOG_SITE_CONFIGS.get(provider, {}).get(
                    "provider_index_refresh_hours", 24.0
                )
            )
            state = upsert_provider_title_index_state(
                session,
                provider=provider,
                slug=slug,
                attempted_at=utcnow(),
                commit=False,
            )
            upsert_provider_title_index_state(
                session,
                provider=provider,
                slug=slug,
                failure_count=state.failure_count + 1,
                last_error_summary=reason[:500],
                commit=False,
            )
            upsert_provider_index_status(
                session,
                provider=provider,
                refresh_interval_hours=refresh_interval_hours,
                status="running",
                current_generation=current.current_generation
                if current is not None
                else None,
                cursor_title_slug=slug,
                last_error_summary=reason[:500],
                commit=False,
            )
            session.commit()

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

    def _stale_generation(self, status) -> str | None:
        current_generation = getattr(status, "current_generation", None)
        latest_success_generation = getattr(status, "latest_success_generation", None)
        if not current_generation:
            return None
        if status.status == "running":
            return current_generation
        if current_generation != latest_success_generation:
            return current_generation
        return None

    def _set_progress(
        self,
        provider: str,
        *,
        phase: str | None = None,
        crawled_titles: int | None = None,
        persisted_titles: int | None = None,
        failed_titles: int | None = None,
        total_titles: int | None | object = _UNSET,
        current_slug: str | None = None,
        queue_depth: int | None = None,
        reset_log_steps: bool = False,
    ) -> None:
        with self._progress_lock:
            snapshot = self._progress.get(provider)
            if snapshot is None:
                snapshot = ProviderCatalogProgress(provider=provider)
                self._progress[provider] = snapshot
            if phase is not None:
                snapshot.phase = phase
            if crawled_titles is not None:
                snapshot.crawled_titles = crawled_titles
            if persisted_titles is not None:
                snapshot.persisted_titles = persisted_titles
            if failed_titles is not None:
                snapshot.failed_titles = failed_titles
            if total_titles is not _UNSET:
                snapshot.total_titles = total_titles
            if current_slug is not None:
                snapshot.current_slug = current_slug
            if queue_depth is not None:
                snapshot.queue_depth = queue_depth
            if reset_log_steps:
                snapshot.last_logged_crawl_step = -1
                snapshot.last_logged_persist_step = -1

    def _advance_crawl_progress(
        self,
        provider: str,
        *,
        current_slug: str,
        queue_depth: int,
    ) -> None:
        with self._progress_lock:
            snapshot = self._progress.setdefault(
                provider, ProviderCatalogProgress(provider=provider)
            )
            snapshot.crawled_titles += 1
            snapshot.current_slug = current_slug
            snapshot.queue_depth = queue_depth
            self._maybe_log_progress(snapshot, kind="crawl")

    def _advance_failed_progress(
        self,
        provider: str,
        *,
        current_slug: str,
        queue_depth: int,
    ) -> None:
        with self._progress_lock:
            snapshot = self._progress.setdefault(
                provider, ProviderCatalogProgress(provider=provider)
            )
            snapshot.failed_titles += 1
            snapshot.current_slug = current_slug
            snapshot.queue_depth = queue_depth
            self._maybe_log_progress(snapshot, kind="crawl")

    def _advance_persist_progress(
        self,
        provider: str,
        *,
        current_slug: str,
        count: int,
        queue_depth: int,
    ) -> None:
        with self._progress_lock:
            snapshot = self._progress.setdefault(
                provider, ProviderCatalogProgress(provider=provider)
            )
            snapshot.phase = "persisting_titles"
            snapshot.persisted_titles += count
            snapshot.current_slug = current_slug
            snapshot.queue_depth = queue_depth
            self._maybe_log_progress(snapshot, kind="persist")

    def _maybe_log_progress(
        self,
        snapshot: ProviderCatalogProgress,
        *,
        kind: str,
    ) -> None:
        if snapshot.total_titles is None:
            return
        step = max(1, int(PROGRESS_STEP_PERCENT))
        if kind == "crawl":
            percent = snapshot.crawl_percent
            current_step = int(percent or 0.0) // step
            if (
                percent is not None
                and percent < 100.0
                and current_step <= snapshot.last_logged_crawl_step
            ):
                return
            snapshot.last_logged_crawl_step = current_step
            logger.info(
                "Provider catalog {} progress [crawl]: crawled={} failed={} persisted={} total={} crawl_percent={} queue_depth={} lag={} current={}",
                snapshot.provider,
                snapshot.crawled_titles,
                snapshot.failed_titles,
                snapshot.persisted_titles,
                snapshot.total_titles,
                percent,
                snapshot.queue_depth,
                snapshot.writer_lag_titles,
                snapshot.current_slug,
            )
            return
        percent = snapshot.progress_percent
        current_step = int(percent or 0.0) // step
        if (
            percent is not None
            and percent < 100.0
            and current_step <= snapshot.last_logged_persist_step
        ):
            return
        snapshot.last_logged_persist_step = current_step
        logger.info(
            "Provider catalog {} progress [persist]: persisted={} total={} percent={} queue_depth={} lag={} current={}",
            snapshot.provider,
            snapshot.persisted_titles,
            snapshot.total_titles,
            percent,
            snapshot.queue_depth,
            snapshot.writer_lag_titles,
            snapshot.current_slug,
        )

    def _get_total_titles(self, provider: str) -> int | None:
        with self._progress_lock:
            snapshot = self._progress.get(provider)
            return None if snapshot is None else snapshot.total_titles

    def _get_persisted_titles(self, provider: str) -> int:
        with self._progress_lock:
            snapshot = self._progress.get(provider)
            return 0 if snapshot is None else snapshot.persisted_titles

    def _get_failed_titles(self, provider: str) -> int:
        with self._progress_lock:
            snapshot = self._progress.get(provider)
            return 0 if snapshot is None else snapshot.failed_titles

    def _get_writer_lag(self, provider: str) -> int:
        with self._progress_lock:
            snapshot = self._progress.get(provider)
            return 0 if snapshot is None else snapshot.writer_lag_titles
