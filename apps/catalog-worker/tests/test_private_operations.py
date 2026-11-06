"""Finite normal collection, restart, partial publication and backup ownership."""

import asyncio
import json
import sys
import time

import pytest
from catalog_core.protocol import Request
from catalog_core.providers.transport import Fetch
from catalog_worker import cli
from catalog_worker.backup import backup
from catalog_worker.collector import Collector
from catalog_worker.config import load
from catalog_worker.operator_status import report
from catalog_worker.query_reader import execute


@pytest.mark.skipif(
    sys.platform != "linux", reason="collector child resource bounds require Linux"
)
def test_normal_multi_provider_command_resumes_and_keeps_failed_provider(
    tmp_path, monkeypatch
):
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "providers": {
                    "aniworld.to": "https://ani.invalid",
                    "s.to": "https://sto.invalid",
                },
                "canonical_sources": {"tv": "off", "movie": "off"},
                "state_dir": str(tmp_path / "state"),
                "output_dir": str(tmp_path / "read"),
                "source_id": "operations",
                "limits": {"publish_interval_s": 300},
            }
        )
    )
    fail = False
    fetched = []

    async def fetch(origin, path, **options):
        provider = "s.to" if "sto.invalid" in origin else "aniworld.to"
        fetched.append((provider, path))
        if fail and provider == "s.to":
            return Fetch("challenge_or_block")
        title = "/serie/ordinary" if provider == "s.to" else "/anime/stream/ordinary"
        episode = title + "/staffel-1/episode-1"
        if path == "/neue-episoden":
            body = (
                '<html><body><div class="newEpisodeList"></div></body></html>'
                if provider == "aniworld.to"
                else '<html><body><table class="new-episodes-table"></table></body></html>'
            )
        elif path in ("/animes-alphabet", "/serien"):
            body = f'<html><body><a href="{title}">Ordinary</a></body></html>'
        elif path == title:
            body = f'<html><body><h1>Ordinary</h1><a href="{episode}">A unique title</a></body></html>'
        elif provider == "s.to":
            body = '<html><body><h1>Episode</h1><button data-play-url="/player" data-provider-name="Vidoza" data-language-label="Deutsch"></button></body></html>'
        else:
            body = '<html><body><h1>Episode</h1><div class="hosterSiteVideo"><li data-lang-key="1" data-link-target="/player"></li></div></body></html>'
        return Fetch("ok", body.encode())

    monkeypatch.setattr(
        cli, "Collector", lambda config, state: Collector(config, state, fetcher=fetch)
    )
    for _ in range(4):
        asyncio.run(cli.collect(config_file, once=True))
    config = load(config_file)
    for provider in config.providers:
        response = execute(
            config.output_dir,
            Request(
                operation="recent", provider=provider, params={"t": "search"}, limit=100
            ),
            int(time.time()),
        )
        assert response.total == 1
    assert len(fetched) == 8
    status = report(config)
    assert all(
        p["mapping"]["episode_mapped"] == 0 and p["counts"]["release"] == 1
        for p in status["providers"].values()
    )
    # Force a fresh listing to demonstrate a blocked provider cannot erase old
    # data or stop another provider's published API from serving.
    import sqlite3
    from contextlib import closing

    for provider in config.providers:
        with (
            closing(sqlite3.connect(config.state_dir / f"{provider}.sqlite")) as db,
            db,
        ):
            db.execute("UPDATE worker_meta SET next_listing=0")
    fail = True
    asyncio.run(cli.collect(config_file, once=True))
    assert report(config)["providers"]["s.to"]["state"] == "blocked"
    assert (
        execute(
            config.output_dir,
            Request(
                operation="recent", provider="s.to", params={"t": "search"}, limit=100
            ),
            int(time.time()),
        ).total
        == 1
    )
    path = backup(config)
    assert len(list(path.glob("*.sqlite"))) == 2
    with pytest.raises(ValueError, match="already exists"):
        backup(config)


def test_failed_backup_set_cannot_be_restored(tmp_path):
    import sqlite3

    from catalog_worker.config import LIMITS, Config

    config = Config(
        {"aniworld.to": "https://fixture.invalid"},
        {"tv": "off"},
        tmp_path / "state",
        tmp_path / "read",
        tmp_path / "unused",
        "backup-test",
        "127.0.0.1",
        8080,
        {key: value[0] for key, value in LIMITS.items()},
    )
    config.state_dir.mkdir()
    (config.state_dir / "aniworld.to.sqlite").write_bytes(b"not a SQLite database")
    with pytest.raises(sqlite3.DatabaseError):
        backup(config)
    assert (config.state_dir / "backup/INCOMPLETE").is_file()
    with pytest.raises(ValueError, match="already exists"):
        backup(config)
