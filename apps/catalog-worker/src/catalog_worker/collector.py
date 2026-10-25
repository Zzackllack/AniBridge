"""One persisted page checkpoint at a time; provider failures stay independent."""

import asyncio
import json
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from catalog_core.diagnostics import reason
from catalog_core.json_codec import require
from catalog_core.providers.aniworld import EpisodeRow
from catalog_core.providers.recent import Change, Window, signal_path
from catalog_core.providers.transport import AdmissionDeferred, Session
from catalog_core.supervisor import run_child_async

from .adapters import listing_path
from .aniworld import Link, Page
from .config import Config
from .fetch_slot import FetchSlot
from .listing import Links, Traversal
from .signals import Signals
from .state import State
from .transactions import atomic


@dataclass(frozen=True)
class Plan:
    now: int
    listing: bool
    work: dict | None
    path: str | None
    started: float = field(default_factory=time.monotonic)
    circuit_lease: int | None = None
    signal: bool = False
    fetch_slot: FetchSlot | None = None


@dataclass(frozen=True)
class Ready:
    plan: Plan
    page: Page | None
    outcome: str = "ok"
    retry_after: int | None = None
    window: Window | None = None
    status: int | None = None
    error_class: str | None = None
    requests: int = 0
    network_s: float = 0
    parser_s: float = 0
    parser_reason: str | None = None
    child_exit: int | None = None


class Collector:
    def __init__(
        self, config: Config, state: State, fetcher=None, clock=time.time
    ) -> None:
        self.session = None
        if fetcher is None:
            if state.provider == "megakino":
                from catalog_core.providers.megakino_session import fetch as fetcher
            else:
                self.session = Session(
                    config.providers[state.provider],
                    config.provider_limits(state.provider)["provider_concurrency"],
                    config.headers(state.provider),
                )
                fetcher = self.session.fetch
        self.config, self.state, self.fetcher, self.clock = (
            config,
            state,
            fetcher,
            clock,
        )

    async def before_request(
        self, *, reconciliation: bool = False, fetch_slot: FetchSlot | None = None
    ) -> None:
        limits = self.config.provider_limits(self.state.provider)
        while True:
            now = int(self.clock())
            budget = self.state.budget_delay(
                now, limits["provider_requests_per_hour"], reconciliation=reconciliation
            )
            if budget:
                raise AdmissionDeferred(budget)
            delay = self.state.request_delay(
                now,
                limits["provider_request_interval_s"],
                limits["provider_requests_per_hour"],
                reconciliation=reconciliation,
            )
            if delay:
                # A redirect resumes in this transport attempt. Restarting the
                # original hop after each spacing deferral could loop forever.
                # These short waits sit outside HTTP deadlines and relinquish
                # global fetch capacity; hourly waits still checkpoint and exit.
                if fetch_slot is not None:
                    await fetch_slot.pause(delay)
                else:
                    await asyncio.sleep(delay)
                continue
            if self.state.allow_request(
                now,
                limits["provider_request_interval_s"],
                limits["provider_requests_per_hour"],
                reconciliation=reconciliation,
            ):
                return

    def admission_delay(self) -> int:
        limits = self.config.provider_limits(self.state.provider)
        return self.state.request_delay(
            int(self.clock()),
            limits["provider_request_interval_s"],
            limits["provider_requests_per_hour"],
        )

    async def close(self) -> None:
        if self.session is not None:
            await self.session.close()

    def prepare(
        self, listing_allowed: bool = True, signal_allowed: bool = True
    ) -> Plan | None:
        """Reserve one durable page; callers serialize this SQLite boundary."""
        config, state = self.config, self.state
        now = state.clock(int(self.clock()))
        if self.admission_delay():
            return None
        meta = state.meta()
        if meta["blocked_until"] > now:
            return None
        from .storage import check

        check(config)
        recent = (
            bool(meta["listing_checked_at"])
            and signal_allowed
            and Signals(state).reserve(
                now, config.providers[state.provider], config.limits["title_deadline_s"]
            )
        )
        listing = not recent and listing_allowed and meta["next_listing"] <= now
        work = (
            None
            if listing or recent
            else state.claim(
                now,
                config.limits["title_deadline_s"],
                incremental=True,
                reconciliation_s=config.limits["historical_interval_s"],
                active_s=config.limits["active_interval_s"],
                hourly=config.provider_limits(state.provider)[
                    "provider_requests_per_hour"
                ],
            )
        )
        if (
            work is not None
            and state.provider == "megakino"
            and not work["path"].startswith("/films/")
        ):
            # Retain explicit unknown-series inventory without repeatedly parsing
            # it as a movie and poisoning the provider circuit.
            with atomic(state.db):
                state.db.execute(
                    "UPDATE work SET due=?,lease_until=0 WHERE path=?",
                    (now + config.limits["historical_interval_s"], work["path"]),
                )
            return None
        if not listing and not recent and work is None:
            return None
        traversal = Traversal(state.db) if listing else None
        path = (
            signal_path(state.provider)
            if recent
            else (
                traversal.next_path(listing_path(state.provider))
                if listing
                else work["path"]
            )
        )
        circuit_lease = None
        if meta["blocked_until"] and path is not None:
            # Reuse the durable cooldown deadline as a finite probe lease. A
            # sibling/restarted producer waits; only this positive page may
            # clear this exact lease, never a later observed provider block.
            circuit_lease = now + config.limits["title_deadline_s"]
            with atomic(state.db):
                state.db.execute(
                    "UPDATE worker_meta SET blocked_until=?", (circuit_lease,)
                )
        return Plan(
            now, listing, work, path, circuit_lease=circuit_lease, signal=recent
        )

    async def collect(self, plan: Plan) -> Ready:
        """Only transport/parsing runs concurrently; no observations mutate here."""
        remaining = self.config.limits["title_deadline_s"] - (
            time.monotonic() - plan.started
        )
        async with asyncio.timeout(max(0, remaining)):
            try:
                return await self._collect(plan)
            except AdmissionDeferred as exc:
                return Ready(
                    plan,
                    None,
                    "admission_deferred",
                    exc.seconds,
                    requests=exc.requests,
                    network_s=exc.duration_s,
                )

    async def _collect(self, plan: Plan) -> Ready:
        config, state = self.config, self.state
        path, listing = plan.path, plan.listing
        if path is None:
            return Ready(plan, Page(Links(state.db), (), 0, None))
        starts = 0

        async def before_request() -> None:
            nonlocal starts
            require(
                starts < config.limits["title_requests_per_slice"],
                "title_request_limit",
            )
            await self.before_request(
                fetch_slot=plan.fetch_slot,
                reconciliation=bool(
                    plan.work
                    and plan.work.get("incremental")
                    and not plan.work.get("targeted")
                    and not plan.work.get("batch_bootstrap")
                    and plan.work["checked_at"] is not None
                ),
            )
            starts += 1

        target = urlsplit(path)
        options = {"query": dict(parse_qsl(target.query))} if target.query else {}
        result = await self.fetcher(
            config.providers[state.provider],
            target.path,
            **options,
            body_bytes=config.limits["body_bytes"],
            deadline=config.limits["request_deadline_s"],
            before_request=before_request,
        )
        if result.outcome != "ok":
            return Ready(
                plan,
                None,
                result.outcome,
                result.retry_after,
                status=result.status,
                error_class=result.error_class,
                requests=result.requests,
                network_s=result.duration_s,
            )
        parser_started = time.monotonic()
        try:
            with tempfile.TemporaryDirectory(
                dir=config.state_dir, prefix="parse-"
            ) as directory:
                source, destination = (
                    Path(directory) / "body",
                    Path(directory) / "records",
                )
                source.write_bytes(result.body)
                await run_child_async(
                    "catalog_worker.parse_child",
                    [
                        str(source),
                        str(destination),
                        "signal" if plan.signal else "listing" if listing else "detail",
                        path,
                        state.provider,
                        config.providers[state.provider],
                        json.dumps(config.sitemap_origins.get(state.provider, [])),
                    ],
                    config.limits["request_deadline_s"],
                )
                data = json.loads(destination.read_bytes())
                if plan.signal:
                    return Ready(
                        plan,
                        None,
                        window=Window(
                            tuple(Change(**entry) for entry in data["entries"]),
                            data["unknown_languages"],
                            data["pagination"],
                        ),
                        status=result.status,
                        requests=result.requests,
                        network_s=result.duration_s,
                        parser_s=time.monotonic() - parser_started,
                    )
                page = Page(
                    tuple(
                        Link(link["path"], link["name"], tuple(link["aliases"]))
                        for link in data["links"]
                    ),
                    tuple(data["languages"]),
                    data["unknown_languages"],
                    data["title"],
                    tuple(data["next_pages"]),
                    data["year"],
                    data["explicit_imdb"],
                    tuple(data["aliases"]),
                    data["episode_title"],
                    tuple(data.get("episode_aliases", [])),
                    tuple(EpisodeRow(**row) for row in data.get("episodes", [])),
                    data.get("availability", "available"),
                )
        except (ValueError, UnicodeError, TimeoutError) as exc:
            return Ready(
                plan,
                None,
                "unexpected_structure",
                error_class=type(exc).__name__,
                parser_reason=getattr(exc, "reason", reason(exc)),
                child_exit=getattr(exc, "exit_code", None),
                status=result.status,
                requests=result.requests,
                network_s=result.duration_s,
                parser_s=time.monotonic() - parser_started,
            )
        return Ready(
            plan,
            page,
            status=result.status,
            requests=result.requests,
            network_s=result.duration_s,
            parser_s=time.monotonic() - parser_started,
        )

    def apply(self, ready: Ready) -> None:
        """Count queue and writer time in the page slice's cumulative deadline."""
        with atomic(self.state.db):
            self.state.db.execute(
                "UPDATE collection_stats SET started_at=CASE WHEN started_at=0 THEN ? ELSE started_at END,"
                "requests=requests+?,pages=pages+?,batch_rows=batch_rows+?,network_ms=network_ms+?,parser_ms=parser_ms+?,"
                "failures=failures+?,admission_deferrals=admission_deferrals+?",
                (
                    ready.plan.now,
                    ready.requests,
                    int(ready.outcome == "ok"),
                    len(ready.page.episodes) if ready.page else 0,
                    int(ready.network_s * 1000),
                    int(ready.parser_s * 1000),
                    int(
                        ready.outcome
                        not in (
                            "ok",
                            "admission_deferred",
                            "local_deadline",
                            "local_resource",
                        )
                    ),
                    int(ready.outcome == "admission_deferred"),
                ),
            )
        deadline = ready.plan.started + self.config.limits["title_deadline_s"]
        if ready.outcome != "ok":
            self._apply(ready)
            return
        if time.monotonic() >= deadline:
            self._apply(Ready(ready.plan, None, "local_deadline"))
            return
        self.state.db.set_progress_handler(lambda: time.monotonic() >= deadline, 1000)
        try:
            require(time.monotonic() < deadline, "title_deadline")
            self._apply(ready)
        except ValueError:
            if ready.plan.signal:
                # Admission overflow rolls back the observation and then exposes
                # the gap. Keep the old window, and retry after consumers drain.
                Signals(self.state).failed(ready.plan.now, 900)
            raise
        finally:
            self.state.db.set_progress_handler(None, 0)

    def _apply(self, ready: Ready) -> None:
        """One checkpoint transaction admits a complete observation or failure."""
        if ready.outcome in ("admission_deferred", "local_deadline", "local_resource"):
            self.state.defer(ready.plan, int(self.clock()), ready.retry_after or 1)
            return
        if ready.outcome != "ok":
            self.state.failure(
                ready.plan.work,
                ready.outcome,
                ready.plan.now,
                ready.retry_after,
                status=ready.status,
                parser_reason=ready.parser_reason,
            )
            if ready.plan.signal:
                Signals(self.state).failed(ready.plan.now, 900)
            elif ready.plan.work:
                Signals(self.state).settle(
                    ready.plan.work, ready.plan.now, success=False
                )
            return
        with atomic(self.state.db):
            if ready.plan.path is not None:
                self.state.success()
            if ready.plan.circuit_lease is not None:
                self.state.db.execute(
                    "UPDATE worker_meta SET blocked_until=0,block_count=0 WHERE blocked_until=?",
                    (ready.plan.circuit_lease,),
                )
            if ready.plan.signal:
                Signals(self.state).accept(
                    ready.window,
                    ready.plan.now,
                    self.config.limits["signal_interval_s"],
                )
            else:
                self._admit(ready)
                if ready.plan.work:
                    Signals(self.state).settle(
                        ready.plan.work, ready.plan.now, success=True
                    )

    def _admit(self, ready: Ready) -> None:
        config, state = self.config, self.state
        plan, page = ready.plan, ready.page
        listing, work, now, path = plan.listing, plan.work, plan.now, plan.path
        if listing:
            traversal = Traversal(state.db)
            if path is None:
                state.listing(
                    page,
                    now,
                    config.limits["listing_interval_s"],
                    accepted=traversal.clear,
                )
                return
            try:
                complete = traversal.add(path, page, config.limits["writer_batch_size"])
            except ValueError:
                with atomic(state.db):
                    traversal.clear()
                state.failure(None, "unexpected_structure", now)
                return
            # Positive pages can be useful before the enumeration is finished.
            # Only a complete traversal supplies disappearance evidence.
            with atomic(state.db):
                for link in page.links:
                    state.discover(link, now)
                state.db.execute("UPDATE worker_meta SET dirty=1")
            if complete:
                state.listing(
                    Page(Links(state.db), (), 0, None),
                    now,
                    config.limits["listing_interval_s"],
                    accepted=traversal.clear,
                )
        else:
            state.detail(
                work,
                page,
                now,
                config.limits["active_interval_s"],
                config.limits["historical_interval_s"],
            )

    async def tick(self) -> bool:
        """Single-page compatibility entry point for operator/fixture procedures."""
        plan = self.prepare()
        if plan is None:
            return False
        self.apply(await self.collect(plan))
        return True
