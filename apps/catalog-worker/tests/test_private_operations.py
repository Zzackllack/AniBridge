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


@pytest.mark.skipif(
    sys.platform != "linux", reason="collector child resource bounds require Linux"
)
def test_once_mode_cancels_and_joins_sibling_maintain_tasks(tmp_path, monkeypatch):
    """A failing maintain coroutine must not orphan the other provider's task."""
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
                "source_id": "once-cleanup",
            }
        )
    )
    cancelled = asyncio.Event()
    closed = []

    class FailingEnricher:
        last_work = "idle"

        def __init__(self, *args, **kwargs):
            pass

        async def tick(self, state, now, *, title_id=None):
            if state.provider == "aniworld.to":
                raise RuntimeError("injected maintain failure")
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        async def close(self):
            closed.append(True)

    class NoCollect:
        def __init__(self, *args, **kwargs):
            pass

        async def run(self, once=False):
            assert once

    monkeypatch.setattr(cli, "Enricher", FailingEnricher)
    monkeypatch.setattr(cli, "Pipeline", NoCollect)
    with pytest.raises(RuntimeError, match="injected maintain failure"):
        asyncio.run(cli.collect(config_file, once=True))
    assert cancelled.is_set() and closed == [True]
    # The process lock must be released after the failed once-mode run.
    from catalog_core.files import ProcessLock

    ProcessLock(tmp_path / "state" / "worker.lock").close()


def test_provider_contract_error_is_retried_without_stopping_other_providers(
    tmp_path, monkeypatch
):
    """Qualified H2 mechanism: a tick exception is retried, not a run crash.

    The first-worker report claimed a whole-collector/gather crashloop for
    descriptor-budget/storage errors. Baseline ``cli.collect`` already caught
    ``ValueError`` (and ``ContractError`` is one) in the maintain loop; the real
    defect was the missing per-title durable backoff. This regression pins that
    a failing provider is retried on the next maintain tick while the other
    provider keeps ticking.
    """
    from types import SimpleNamespace

    from catalog_core.json_codec import ContractError

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
                "source_id": "contract-retry",
            }
        )
    )
    ticks = {"aniworld.to": 0, "s.to": 0}

    class FailingEnricher:
        last_work = "idle"

        def __init__(self, *args, **kwargs):
            pass

        async def tick(self, state, now, *, title_id=None):
            ticks[state.provider] += 1
            if state.provider == "aniworld.to":
                raise ContractError("descriptor_budget")
            return True

        async def close(self):
            pass

    class StubCollector:
        def __init__(self, *args, **kwargs):
            pass

        async def close(self):
            pass

    class StubPipeline:
        def __init__(self, *args, **kwargs):
            pass

        async def run(self, once=False):
            pass

    monkeypatch.setattr(cli, "Enricher", FailingEnricher)
    monkeypatch.setattr(cli, "Collector", StubCollector)
    monkeypatch.setattr(cli, "Pipeline", StubPipeline)
    # collect() refuses non-Linux hosts before the loop; the loop itself is
    # platform-neutral once collectors are stubbed.
    monkeypatch.setattr(cli, "sys", SimpleNamespace(platform="linux"))

    async def scenario():
        task = asyncio.create_task(cli.collect(config_file, once=False))
        try:
            async with asyncio.timeout(10):
                while ticks["aniworld.to"] < 2 or ticks["s.to"] < 2:
                    await asyncio.sleep(0.01)
            assert ticks["aniworld.to"] >= 2
            assert ticks["s.to"] >= 2
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


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


def test_backup_syncs_copied_databases_before_clearing_the_fence(tmp_path, monkeypatch):
    from test_pipeline import collectors

    from catalog_worker import backup as module

    group = collectors(tmp_path)
    try:
        config = group[0].config
        fence = config.state_dir / "backup" / "INCOMPLETE"
        synced = []
        original = module._sync_file

        def observed(path):
            # The set must not look restorable before its bytes are durable.
            synced.append((path.name, fence.exists()))
            original(path)

        monkeypatch.setattr(module, "_sync_file", observed)
        root = backup(config)
        assert synced == [
            ("aniworld.to.sqlite", True),
            ("s.to.sqlite", True),
            ("megakino.sqlite", True),
        ]
        assert not fence.exists()
        assert sorted(path.name for path in root.glob("*.sqlite")) == [
            "aniworld.to.sqlite",
            "megakino.sqlite",
            "s.to.sqlite",
        ]
    finally:
        for collector in group:
            collector.state.close()


def test_generated_token_file_is_private_from_creation(tmp_path):
    import stat

    from catalog_worker.pilot_seed import _private_write

    path = tmp_path / "metadata-token"
    _private_write(path, b"secret")
    assert path.read_bytes() == b"secret"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        _private_write(path, b"replacement")
    assert path.read_bytes() == b"secret"
