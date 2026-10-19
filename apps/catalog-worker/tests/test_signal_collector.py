"""Actual bounded parser children; transport remains generated and test-only."""

import asyncio
import sys

import pytest
from catalog_core.providers.recent import Change, Window
from catalog_worker.aniworld import Link, Page
from catalog_worker.collector import Collector, Plan, Ready
from catalog_worker.config import LIMITS, Config
from catalog_worker.signals import Signals
from catalog_worker.state import State
from catalog_worker.transport import Fetch

NOW = 1800000000


@pytest.mark.skipif(sys.platform != "linux", reason="Linux parser limits")
@pytest.mark.parametrize("provider", ["aniworld.to", "s.to"])
def test_default_signal_route_fetches_only_missing_parents_and_advertised_episode(
    tmp_path, provider
):
    prefix = "/anime/stream/" if provider == "aniworld.to" else "/serie/"
    title = prefix + "example"
    episode = title + "/staffel-1/episode-2"
    if provider == "aniworld.to":
        recent = f'<div class="newEpisodeList"><div class="row"><a href="{episode}"><strong>Example</strong></a><img data-src="/public/img/german.svg"></div></div>'
        detail = '<h1>Example</h1><small class="episodeEnglishTitle">Two</small><div class="hosterSiteVideo"><li data-lang-key="1" data-link-target="/private"></li></div>'
    else:
        recent = f'<table class="new-episodes-table"><tr><td><a href="{episode}">Example</a></td><td><svg title="Deutsch"></svg></td></tr></table>'
        detail = '<h1>Example</h1><h2>S01E02: Zwei (Two)</h2><button data-play-url="/private" data-provider-name="VOE" data-language-label="Deutsch"></button>'
    pages = {
        "/animes-alphabet"
        if provider == "aniworld.to"
        else "/serien": f'<a href="{title}">Example</a>',
        "/neue-episoden": recent,
        title: f'<h1>Example</h1><a href="{title}/staffel-1">Season</a><a href="{title}/staffel-2">Unchanged history</a>',
        title
        + "/staffel-1": f'<a href="{episode}">Two</a><a href="{title}/staffel-1/episode-1">Old</a>',
        episode: detail,
    }
    state = State(tmp_path / "worker.sqlite", provider)
    config = Config(
        {provider: "https://fixture.invalid"},
        {"tv": "off"},
        tmp_path,
        tmp_path / "out",
        tmp_path / "key",
        "fixture",
        "127.0.0.1",
        1,
        {k: v[0] for k, v in LIMITS.items()},
    )
    now = NOW
    calls = []

    async def fetcher(origin, path, **options):
        await options["before_request"]()
        calls.append(path)
        return Fetch("ok", ("<html><body>" + pages[path] + "</body></html>").encode())

    collector = Collector(config, state, fetcher=fetcher, clock=lambda: now)
    try:
        for _ in range(5):
            now += 3
            assert asyncio.run(collector.tick())
        assert calls == list(pages)
        assert Signals(state).status()["pending"] == 0
        assert (
            state.db.execute("SELECT language FROM release").fetchone()[0] == "de-dub"
        )
        assert (
            state.db.execute("SELECT detail_status FROM title").fetchone()[0]
            == "partial"
        )
        now += 900
        assert asyncio.run(collector.tick())
        assert (
            calls[-1] == "/neue-episoden"
            and Signals(state).status()["coverage"] == "window-overlap"
        )
        assert not asyncio.run(collector.tick())
        state.close()
        state = State(tmp_path / "worker.sqlite", provider)
        assert Signals(state).status()["pending"] == 0
    finally:
        state.close()


def test_detail_and_signal_acknowledgement_share_one_atomic_checkpoint(
    tmp_path, monkeypatch
):
    state = State(tmp_path / "worker.sqlite", "aniworld.to")
    title = "/anime/stream/example"
    episode = title + "/staffel-1/episode-1"
    state.listing(Page((Link(title, "Example"),), (), 0, None), NOW)
    with state.db:
        state.db.execute("UPDATE work SET checked_at=?,due=?", (NOW, NOW + 604800))
    Signals(state).accept(
        Window((Change(episode, "Example", "de-dub"),), 0), NOW + 1, 900
    )
    work = state.claim(NOW + 1, incremental=True)
    # Missing season is processed first; the release case needs the episode reservation.
    if work["kind"] == "season":
        state.detail(work, Page((), (), 0, None), NOW + 1)
        Signals(state).settle(work, NOW + 1, success=True)
        work = state.claim(NOW + 1, incremental=True)
    before = state.db.execute("SELECT count(*) FROM release").fetchone()[0]
    config = Config(
        {"aniworld.to": "https://fixture.invalid"},
        {"tv": "off"},
        tmp_path,
        tmp_path / "out",
        tmp_path / "key",
        "fixture",
        "127.0.0.1",
        1,
        {k: v[0] for k, v in LIMITS.items()},
    )

    def broken(*args, **kwargs):
        raise RuntimeError("ack checkpoint injection")

    monkeypatch.setattr(Signals, "settle", broken)
    with pytest.raises(RuntimeError, match="checkpoint injection"):
        Collector(config, state).apply(
            Ready(
                Plan(NOW + 1, False, work, work["path"]),
                Page((), ("de-dub",), 0, None, episode_title="One"),
            )
        )
    assert state.db.execute("SELECT count(*) FROM release").fetchone()[0] == before
    assert Signals(state).status()["pending"] == 1
    state.close()


def test_writer_overflow_latches_gap_and_keeps_last_observed_window(
    tmp_path, monkeypatch
):
    import catalog_worker.signals as module

    state = State(tmp_path / "worker.sqlite", "aniworld.to")
    signals = Signals(state)
    signals.accept(Window((), 0), NOW, 900)
    previous = signals.status()
    monkeypatch.setattr(module, "MAX_PENDING", 1)
    config = Config(
        {"aniworld.to": "https://fixture.invalid"},
        {"tv": "off"},
        tmp_path,
        tmp_path / "out",
        tmp_path / "key",
        "fixture",
        "127.0.0.1",
        1,
        {k: v[0] for k, v in LIMITS.items()},
    )
    with pytest.raises(ValueError, match="pending overflow"):
        Collector(config, state).apply(
            Ready(
                Plan(NOW + 901, False, None, "/neue-episoden", signal=True),
                None,
                window=Window(
                    (Change("/anime/stream/new/staffel-1/episode-1", "New", "de-dub"),),
                    0,
                ),
            )
        )
    current = signals.status()
    assert current["checked_at"] == previous["checked_at"]
    assert current["coverage"] == "gap" and current["lease_until"] == 0
    assert (
        current["pending"] == 0
        and state.db.execute("SELECT count(*) FROM title").fetchone()[0] == 0
    )
    state.close()
