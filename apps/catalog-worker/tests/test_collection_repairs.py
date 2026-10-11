"""Focused collector defects: no provider I/O, disposable state only."""

import asyncio

from catalog_core.identity import mapping_id
from catalog_core.providers.aniworld import EpisodeRow, Link, Page
from catalog_core.providers.sto import parse
from catalog_worker.canonical_cache import apply, store
from catalog_worker.collector import Plan
from catalog_worker.mapping import CanonicalEpisode
from catalog_worker.pipeline import Pipeline
from catalog_worker.progress import measure
from catalog_worker.state import State
from test_pipeline import NOW, collectors


def test_exhausted_admission_defers_without_failure_across_restart(tmp_path):
    group = collectors(tmp_path, provider_requests_per_hour=1)
    c = group[0]

    async def fake(origin, path, **kwargs):
        await kwargs["before_request"]()
        raise AssertionError("no HTTP request admitted")

    c.fetcher = fake
    try:
        work = c.state.claim(NOW)
        assert c.state.allow_request(NOW, 2, 1)
        ready = asyncio.run(c.collect(Plan(NOW, False, work, work["path"])))
        assert ready.outcome == "admission_deferred" and ready.retry_after == 3600
        c.apply(ready)
        row = c.state.db.execute(
            "SELECT * FROM work WHERE path=?", (work["path"],)
        ).fetchone()
        assert (
            row["failures"] == 0
            and row["lease_until"] == 0
            and row["due"] == NOW + 3600
        )
        assert c.state.meta()["blocked_until"] == 0
        assert (
            c.state.db.execute("SELECT count(*) FROM transport_failure").fetchone()[0]
            == 0
        )
        filename = tmp_path / "aniworld.to.sqlite"
        c.state.close()
        c.state = State(filename, "aniworld.to")
        assert c.prepare() is None
        c.clock = lambda: NOW + 3600
        assert c.prepare() is not None
    finally:
        for c in group:
            c.state.close()


def test_exhausted_provider_does_not_acquire_fetch_slot(tmp_path):
    group = collectors(tmp_path, fetch_concurrency=1)
    c = group[0]
    try:
        assert c.state.allow_request(NOW, 2, 1)
        c.config.limits["provider_requests_per_hour"] = 1
        pipeline = Pipeline(group, lambda *args: None)

        async def scenario():
            await pipeline.fetch_slots.acquire()
            assert await asyncio.wait_for(pipeline.page(c), 0.1) is False

        asyncio.run(scenario())
    finally:
        for c in group:
            c.state.close()


def test_transient_retry_circuit_success_and_parser_isolation(tmp_path):
    group = collectors(tmp_path)
    c = group[0]
    try:
        work = c.state.claim(NOW)
        c.state.failure(work, "transport_failure", NOW)
        due = c.state.db.execute(
            "SELECT due FROM work WHERE path=?", (work["path"],)
        ).fetchone()[0]
        assert 4 <= due - NOW <= 6 and c.state.meta()["blocked_until"] == 0
        for n in range(1, 8):
            c.state.failure(work, "transport_failure", NOW + n * 5)
        assert NOW + 35 < c.state.meta()["blocked_until"] < NOW + 120
        with c.state.db:
            c.state.success()
        assert (
            c.state.db.execute("SELECT count(*) FROM transport_failure").fetchone()[0]
            == 0
        )
        old = c.state.meta()["blocked_until"]
        c.state.failure(work, "unexpected_structure", NOW + 40)
        assert c.state.meta()["blocked_until"] == old
        c.state.failure(work, "rate_limited", NOW + 100, retry_after=12)
        assert c.state.meta()["blocked_until"] == NOW + 112
    finally:
        for c in group:
            c.state.close()


def test_german_heading_retained_generic_not_mapped(tmp_path):
    for heading in ["Leichtfertige Versprechen", "Folge 1"]:
        page = parse(
            f'<html><body><h1>Example</h1><h2>S01E01: {heading}</h2><button data-provider-name="VOE" data-play-url="/private" data-language-label="Deutsch"></button></body></html>'.encode(),
            "detail",
            "/serie/example/staffel-1/episode-1",
        )
        assert page.episode_title == heading
    state = State(tmp_path / "state.sqlite", "s.to")
    try:
        path = "/serie/example"
        tid = state.discover(Link(path, "Example"), NOW)
        state.db.commit()
        ep = path + "/staffel-8/episode-1"
        state.detail(
            state.claim(NOW), Page((Link(ep, "Episode"),), (), 0, "Example"), NOW
        )
        state.detail(
            state.claim(NOW),
            Page(
                (),
                ("de-dub",),
                0,
                None,
                episode_title="Folge 1",
                episode_aliases=("Leichtfertige Versprechen",),
            ),
            NOW,
        )
        mid = mapping_id("s.to", tid, "tvdb", "123")
        with state.db:
            state.db.execute(
                "INSERT INTO canonical_title VALUES(?,?,?,?,?,?,?)",
                (mid, tid, "tvdb", "123", "synthetic-v1", "reviewed", NOW),
            )
            store(
                state,
                tid,
                "digest",
                "matcher",
                NOW,
                [
                    CanonicalEpisode(2, 7, "Leichtfertige Versprechen"),
                    CanonicalEpisode(8, 1, "Folge 1"),
                ],
            )
            apply(state, tid, NOW)
        assert tuple(
            state.db.execute("SELECT season,episode FROM canonical_episode").fetchone()
        ) == (2, 7)
    finally:
        state.close()


def test_batch_saves_details_preserves_ids_and_missing_changed_evidence(tmp_path):
    state = State(tmp_path / "state.sqlite", "aniworld.to")
    path = "/anime/stream/example"
    season = path + "/staffel-1"
    ep = season + "/episode-1"
    try:
        state.listing(Page((Link(path, "Example"),), (), 0, None), NOW)
        state.detail(
            state.claim(NOW), Page((Link(season, "Season"),), (), 0, "Example"), NOW
        )
        page = Page(
            (Link(ep, "One"),),
            (),
            0,
            None,
            episodes=(EpisodeRow(ep, "One", ("Eins",), ("de-dub", "en-sub")),),
        )
        state.detail(state.claim(NOW), page, NOW)
        assert state.claim(NOW) is None
        before = [
            tuple(r)
            for r in state.db.execute("SELECT * FROM release ORDER BY release_id")
        ]
        with state.db:
            state.db.execute("UPDATE work SET due=0 WHERE path=?", (season,))
        incomplete = Page(
            (Link(ep, "One"),),
            (),
            0,
            None,
            episodes=(EpisodeRow(ep, "One", (), ("de-dub",), 1),),
        )
        state.detail(state.claim(NOW + 1), incomplete, NOW + 1)
        assert state.claim(NOW + 1)["path"] == ep
        assert state.db.execute("SELECT count(*) FROM release").fetchone()[0] == 2
        assert (
            state.db.execute(
                "SELECT count(*) FROM omissions WHERE kind='release'"
            ).fetchone()[0]
            == 0
        )
        assert [
            r[3] for r in state.db.execute("SELECT * FROM release ORDER BY release_id")
        ] == [r[3] for r in before]
    finally:
        state.close()


def test_progress_does_not_confuse_discovery_and_usable_mappings(tmp_path):
    group = collectors(tmp_path)
    c = group[0]
    try:
        result = measure(c.state.db, c.state.meta(), NOW)
        assert not result["first_pass_complete"] and result["discovery_queue_can_grow"]
        assert result["eta_seconds"] is None
    finally:
        for c in group:
            c.state.close()


def test_progress_explains_deferred_bootstrap_and_due_retries(tmp_path):
    from test_signals import TITLE, prepared

    state = prepared(tmp_path)
    try:
        with state.db:
            state.db.execute(
                "UPDATE work SET checked_at=NULL, due=?, failures=1 WHERE path=?",
                (NOW + 3600, TITLE),
            )
        status = measure(state.db, state.meta(), NOW)
        assert status["queue"] == {
            "pending_due_now": 0,
            "pending_deferred": 1,
            "pending_leased": 0,
            "next_pending_due": NOW + 3600,
            "failed_due_now": 0,
        }
        assert not status["first_pass_complete"]
        assert (
            measure(state.db, state.meta(), NOW + 3600)["queue"]["failed_due_now"] == 1
        )
    finally:
        state.close()


def test_upgrade_backlog_refreshes_season_once_before_episode_details(tmp_path):
    state = State(tmp_path / "state.sqlite", "aniworld.to")
    title = "/anime/stream/example"
    season = title + "/staffel-1"
    ep = season + "/episode-1"
    try:
        state.listing(Page((Link(title, "Example"),), (), 0, None), NOW)
        state.detail(
            state.claim(NOW), Page((Link(season, "Season"),), (), 0, "Example"), NOW
        )
        state.detail(state.claim(NOW), Page((Link(ep, "One"),), (), 0, None), NOW)
        with state.db:
            state.db.execute("DELETE FROM season_batch_checkpoint")
        work = state.claim(NOW, incremental=True)
        assert work["path"] == season and work["batch_bootstrap"]
        state.detail(
            work,
            Page(
                (Link(ep, "One"),),
                (),
                0,
                None,
                episodes=(EpisodeRow(ep, "One", (), ("de-dub",)),),
            ),
            NOW,
        )
        assert state.claim(NOW, incremental=True) is None
    finally:
        state.close()


def test_first_pass_can_complete_without_claiming_canonical_or_recent_completeness(
    tmp_path,
):
    from test_signals import prepared

    state = prepared(tmp_path)
    try:
        status = measure(state.db, state.meta(), NOW)
        assert status["first_pass_complete"] and status["detail_evidence_complete"]
        assert (
            status["episodes_with_releases"] == 1
            and status["mapped_with_releases"] == 0
        )
        assert status["mapping_fraction"] == 0
    finally:
        state.close()


def test_short_redirect_spacing_releases_slot_and_resumes_chain(tmp_path, monkeypatch):
    import socket

    import httpx
    from catalog_core.providers.transport import Session
    from catalog_worker.fetch_slot import FetchSlot

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b""

    group = collectors(tmp_path, fetch_concurrency=1)
    c = group[0]
    now = NOW
    calls = []
    ticks = []

    async def advance(seconds):
        nonlocal now
        assert not slot.held and semaphore._value == 1
        ticks.append(seconds)
        now += seconds

    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))]
    )

    def respond(request):
        calls.append(request.url.path)
        return httpx.Response(
            302 if len(calls) == 1 else 200,
            headers={"Location": "/second"} if len(calls) == 1 else {},
            stream=Stream(),
        )

    monkeypatch.setattr(
        httpx, "AsyncHTTPTransport", lambda **k: httpx.MockTransport(respond)
    )
    monkeypatch.setattr(asyncio, "sleep", advance)
    semaphore = asyncio.Semaphore(1)
    slot = FetchSlot(semaphore, lambda delta: None)
    c.clock = lambda: now

    async def scenario():
        session = Session("https://fixture.invalid")
        async with slot:
            try:
                result = await session.fetch(
                    "https://fixture.invalid",
                    "/first",
                    before_request=lambda: c.before_request(fetch_slot=slot),
                )
                assert result.outcome == "ok" and result.requests == 2
            finally:
                await session.close()
        assert semaphore._value == 1 and not slot.held

    try:
        asyncio.run(scenario())
        assert calls == ["/first", "/second"] and ticks == [2]
    finally:
        for c in group:
            c.state.close()


def test_cancelled_spacing_does_not_leak_or_double_release_slot():
    from catalog_worker.fetch_slot import FetchSlot

    async def scenario():
        semaphore = asyncio.Semaphore(1)
        counts = []
        slot = FetchSlot(semaphore, counts.append)

        async def paused():
            async with slot:
                await slot.pause(60)

        task = asyncio.create_task(paused())
        await asyncio.sleep(0)
        assert not slot.held and semaphore._value == 1
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert semaphore._value == 1 and counts == [1, -1]

    asyncio.run(scenario())


def test_redirect_pause_and_single_ready_slot_do_not_deadlock(tmp_path):
    from catalog_worker.collector import Ready

    group = collectors(tmp_path, ready_queue_size=1, fetch_concurrency=1)

    async def collect(plan):
        await plan.fetch_slot.pause(0.01)
        return Ready(plan, Page((), (), 0, "Observed"))

    for collector in group:
        collector.collect = collect

    async def scenario():
        pipeline = Pipeline(group, lambda *args: None)
        await asyncio.wait_for(pipeline.run(once=True), 1)
        assert pipeline.fetching == 0 and pipeline.max_fetching == 1
        assert pipeline.max_ready == 1

    try:
        asyncio.run(scenario())
    finally:
        for collector in group:
            collector.state.close()


def test_positive_season_row_does_not_advance_failed_detail_retry(tmp_path):
    state = State(tmp_path / "state.sqlite", "aniworld.to")
    path = "/anime/stream/example"
    season = path + "/staffel-1"
    ep = season + "/episode-1"
    try:
        state.listing(Page((Link(path, "Example"),), (), 0, None), NOW)
        state.detail(
            state.claim(NOW), Page((Link(season, "Season"),), (), 0, "Example"), NOW
        )
        state.detail(state.claim(NOW), Page((Link(ep, "One"),), (), 0, None), NOW)
        with state.db:
            state.db.execute(
                "UPDATE work SET failures=3,due=? WHERE path=?", (NOW + 300, ep)
            )
            state.db.execute("UPDATE work SET due=0 WHERE path=?", (season,))
        state.detail(
            state.claim(NOW + 1),
            Page(
                (Link(ep, "One"),),
                (),
                0,
                None,
                episodes=(EpisodeRow(ep, "One", (), ("de-dub",)),),
            ),
            NOW + 1,
        )
        row = state.db.execute(
            "SELECT failures,due FROM work WHERE path=?", (ep,)
        ).fetchone()
        assert tuple(row) == (3, NOW + 300)
    finally:
        state.close()


def test_empty_batch_probe_does_not_delay_new_work_or_survive_restart(tmp_path):
    state = State(tmp_path / "state.sqlite", "aniworld.to")
    title = "/anime/stream/example"
    season = title + "/staffel-1"
    ep = season + "/episode-1"
    try:
        state.listing(Page((Link(title, "Example"),), (), 0, None), NOW)
        state.detail(
            state.claim(NOW), Page((Link(season, "Season"),), (), 0, "Example"), NOW
        )
        state.detail(state.claim(NOW), Page((), (), 0, None), NOW)
        assert state.claim(NOW + 1, incremental=True) is None
        with state.db:
            state.db.execute("DELETE FROM season_batch_checkpoint")
            state.db.execute(
                "INSERT INTO work(path,title_id,kind,due) SELECT ?,title_id,'episode',? FROM title",
                (ep, NOW + 2),
            )
        work = state.claim(NOW + 2, incremental=True)
        assert work["path"] == ep  # Empty batch-probe caching never delays new pages.
        state.close()
        state = State(tmp_path / "state.sqlite", "aniworld.to")
        resumed = state.claim(NOW + 3, incremental=True)
        assert resumed["path"] == season and resumed["batch_bootstrap"]
    finally:
        state.close()


def test_named_detail_without_alias_keeps_positive_season_alias(tmp_path):
    state = State(tmp_path / "state.sqlite", "aniworld.to")
    title = "/anime/stream/example"
    season = title + "/staffel-1"
    ep = season + "/episode-1"
    try:
        state.listing(Page((Link(title, "Example"),), (), 0, None), NOW)
        state.detail(
            state.claim(NOW), Page((Link(season, "Season"),), (), 0, "Example"), NOW
        )
        state.detail(
            state.claim(NOW),
            Page(
                (Link(ep, "One"),),
                (),
                0,
                None,
                episodes=(EpisodeRow(ep, "One", ("Eins",), ("de-dub",)),),
            ),
            NOW,
        )
        work = dict(
            state.db.execute("SELECT * FROM work WHERE path=?", (ep,)).fetchone()
        )
        state.detail(work, Page((), ("de-dub",), 0, None, episode_title="One"), NOW + 1)
        assert (
            state.db.execute("SELECT display_title FROM entity_alias").fetchone()[0]
            == "Eins"
        )
        assert (
            state.db.execute("SELECT first_seen_at FROM release").fetchone()[0] == NOW
        )
    finally:
        state.close()
