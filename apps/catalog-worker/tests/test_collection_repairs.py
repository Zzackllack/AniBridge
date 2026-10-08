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
