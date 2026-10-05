"""Targeted collection resumes its real checkpoints, not a fabricated label."""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from catalog_core.providers.transport import Fetch

from catalog_worker import cli
from catalog_worker.collector import Collector
from catalog_worker.state import State


@pytest.mark.skipif(
    sys.platform != "linux", reason="collector child bounds require Linux"
)
def test_two_targeted_passes_preserve_fetched_title(
    tmp_path: Path, monkeypatch
) -> None:
    title = "/anime/stream/a-url-slug"
    heading = "The Proper Display Title"
    episodes = [title + f"/staffel-1/episode-{n}" for n in range(1, 32)]
    fetched: list[str] = []

    async def fetch(origin: str, path: str, **options) -> Fetch:
        fetched.append(path)
        if path == title:
            html = (
                "<html><body><h1>"
                + heading
                + "</h1>"
                + "".join(f'<a href="{episode}">Episode</a>' for episode in episodes)
                + "</body></html>"
            )
        else:
            assert path in episodes
            html = '<html><body><h1>Episode</h1><div class="hosterSiteVideo"><li data-lang-key="1" data-link-target="/redirect/not-fetched"></li></div></body></html>'
        return Fetch("ok", html.encode())

    monkeypatch.setattr(
        cli, "Collector", lambda config, state: Collector(config, state, fetcher=fetch)
    )
    config = tmp_path / "worker.json"
    config.write_text(
        json.dumps(
            {
                "providers": {"aniworld.to": "https://fixture.invalid"},
                "canonical_sources": {"tv": "off", "movie": "off"},
                "state_dir": str(tmp_path / "state"),
                "output_dir": str(tmp_path / "read"),
                "source_id": "resume-test",
            }
        )
    )
    filename = tmp_path / "state" / "aniworld.to.sqlite"
    asyncio.run(cli.collect_title(config, title))
    state = State(filename, "aniworld.to")
    try:
        assert (
            state.db.execute("SELECT display_title FROM title").fetchone()[0] == heading
        )
        before = [
            tuple(row)
            for row in state.db.execute(
                "SELECT release_id,first_seen_at FROM release ORDER BY release_id"
            )
        ]
        assert len(before) == 29
        assert (
            state.db.execute(
                "SELECT count(*) FROM work WHERE checked_at IS NULL"
            ).fetchone()[0]
            == 2
        )
    finally:
        state.close()

    asyncio.run(cli.collect_title(config, title))
    state = State(filename, "aniworld.to")
    try:
        assert (
            state.db.execute("SELECT display_title FROM title").fetchone()[0] == heading
        )
        after = dict(state.db.execute("SELECT release_id,first_seen_at FROM release"))
        assert len(after) == 31 and all(after[key] == seen for key, seen in before)
        assert (
            state.db.execute(
                "SELECT count(*) FROM work WHERE checked_at IS NULL"
            ).fetchone()[0]
            == 0
        )
        assert fetched.count(title) == 1
        assert len(fetched) == 32
    finally:
        state.close()
