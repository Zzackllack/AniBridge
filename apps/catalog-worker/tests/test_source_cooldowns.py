"""Origin pauses are shared, restart-safe, bounded and fail closed."""

import asyncio
import json

import pytest
from catalog_core.providers.transport import AdmissionDeferred, Fetch
from catalog_worker.canonical import Enricher
from catalog_worker.canonical_failures import CanonicalUnavailable
from test_canonical import NOW


@pytest.mark.parametrize(
    "status,outcome", [(429, "rate_limited"), (503, "transport_failure")]
)
def test_origin_pause_survives_new_enricher_and_leaves_other_origin_available(
    tmp_path, status, outcome
):
    path = tmp_path / "canonical-cooldowns.json"
    calls = []
    clock = [NOW + 0.25]

    async def fetch(origin, route, **kwargs):
        calls.append(origin)
        return (
            Fetch(outcome, status=status, retry_after=600)
            if len(calls) == 1
            else Fetch("ok", b"{}")
        )

    async def scenario():
        first = Enricher({}, fetcher=fetch, clock=lambda: clock[0], cooldown_file=path)
        with pytest.raises(CanonicalUnavailable):
            await first.request("/v2/tvdb/search")
        restarted = Enricher(
            {}, fetcher=fetch, clock=lambda: clock[0], cooldown_file=path
        )
        with pytest.raises(AdmissionDeferred) as pause:
            await restarted.request("/v2/tvdb/search")
        assert pause.value.seconds == 601 and len(calls) == 1
        await restarted.request("/v1/movie/1", origin="https://api.radarr.video")
        clock[0] = NOW + 601
        await restarted.request("/v2/tvdb/search")
        assert len(calls) == 3

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "payload",
    [
        b"broken",
        b"x" * 4097,
        b'{"version":1,"until":{"https://unexpected.invalid":100}}',
        b'{"version":1,"until":{"https://skyhook.sonarr.tv":true}}',
    ],
)
def test_corrupt_pause_file_refuses_startup(tmp_path, payload):
    path = tmp_path / "canonical-cooldowns.json"
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        Enricher({}, cooldown_file=path)


def test_failed_pause_write_is_fatal_and_keeps_last_complete_file(
    tmp_path, monkeypatch
):
    from catalog_worker.source_cooldowns import CooldownWriteError, SourceCooldowns

    path = tmp_path / "canonical-cooldowns.json"
    pause = SourceCooldowns(path)
    pause.pause("https://skyhook.sonarr.tv", 60, NOW)
    before = path.read_bytes()

    def failed(*args):
        raise OSError("injected storage failure")

    monkeypatch.setattr("catalog_worker.source_cooldowns.atomic_write", failed)
    with pytest.raises(CooldownWriteError):
        pause.pause("https://skyhook.sonarr.tv", 600, NOW)
    assert path.read_bytes() == before
    assert json.loads(before)["until"]["https://skyhook.sonarr.tv"] == NOW + 60


def test_worker_backup_retains_origin_pause_and_fractional_admission(tmp_path):
    from catalog_worker.backup import backup
    from catalog_worker.source_cooldowns import FILENAME, SourceCooldowns
    from catalog_worker.state import State
    from test_pipeline import collectors

    group = collectors(tmp_path)
    try:
        config = group[0].config
        SourceCooldowns(tmp_path / FILENAME).pause(
            "https://skyhook.sonarr.tv", 600, NOW
        )
        assert group[0].state.allow_request(NOW + 0.125, 0.2, 18000)
        root = backup(config)
        assert (
            SourceCooldowns(root / FILENAME).delay("https://skyhook.sonarr.tv", NOW)
            == 600
        )
        copied = State(root / "aniworld.to.sqlite", "aniworld.to")
        try:
            assert (
                copied.db.execute("SELECT min(at) FROM request_start").fetchone()[0]
                == NOW + 0.125
            )
        finally:
            copied.close()
    finally:
        for collector in group:
            collector.state.close()
