"""Fractional starts retain durable quotas and work with legacy admission rows."""

import asyncio
import json
from itertools import pairwise

import pytest
from test_pipeline import NOW, collectors

from catalog_worker.config import load
from catalog_worker.pipeline import Pipeline
from catalog_worker.state import State


def test_millisecond_profile_keeps_legacy_provider_override(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "providers": {
                    "aniworld.to": "https://aniworld.to",
                    "s.to": "https://serienstream.to",
                },
                "canonical_sources": {},
                "state_dir": str(tmp_path / "state"),
                "output_dir": str(tmp_path / "read"),
                "source_id": "test",
                "limits": {
                    "provider_request_interval_ms": 200,
                    "provider_requests_per_hour": 18000,
                },
                "provider_settings": {
                    "s.to": {"limits": {"provider_request_interval_s": 5}}
                },
            }
        )
    )
    config = load(path)
    assert config.provider_interval("aniworld.to") == 0.2
    assert config.provider_interval("s.to") == 5
    assert config.provider_limits("aniworld.to")["provider_requests_per_hour"] == 18000
    for invalid in [True, -1, 1, 199, 60001, 200.0]:
        data = json.loads(path.read_text())
        data["limits"]["provider_request_interval_ms"] = invalid
        path.write_text(json.dumps(data))
        with pytest.raises(ValueError):
            load(path)


def test_fractional_starts_spacing_hourly_quota_and_restart(tmp_path):
    filename = tmp_path / "state.sqlite"
    state = State(filename, "aniworld.to")
    try:
        now = NOW + 0.125
        for _ in range(5):
            assert state.allow_request(now, 0.2, 5)
            assert not state.allow_request(now + 0.1, 0.2, 5)
            now += 0.2
        assert state.budget_delay(NOW + 1, 5) == 3600
        state.close()
        state = State(filename, "aniworld.to")
        assert not state.allow_request(NOW + 1, 0.2, 5)
        assert not state.allow_request(NOW + 3600, 0.2, 5)
        assert state.allow_request(NOW + 3600.125, 0.2, 5)
        assert state.db.execute("SELECT count(*) FROM request_start").fetchone()[0] == 5
    finally:
        state.close()


def test_producer_waits_only_remaining_spacing(tmp_path, monkeypatch):
    group = collectors(tmp_path)
    pipeline = Pipeline(group, lambda *args: None)
    waits = []

    async def page(collector):
        return False

    async def sleep(delay):
        waits.append(delay)
        raise asyncio.CancelledError

    pipeline.page = page
    group[0].admission_delay = lambda: 0.2
    monkeypatch.setattr("catalog_worker.pipeline.asyncio.sleep", sleep)
    try:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(pipeline.producer(group[0], False))
        assert waits == [0.2]
    finally:
        for collector in group:
            collector.state.close()


def test_concurrent_collector_admission_paces_and_stops_at_hourly_cap(tmp_path):
    import time

    from catalog_core.providers.transport import AdmissionDeferred

    group = collectors(
        tmp_path, provider_request_interval_ms=200, provider_requests_per_hour=5
    )
    c = group[0]
    start = time.monotonic()
    c.clock = lambda: NOW + time.monotonic() - start
    try:

        async def scenario():
            async with asyncio.timeout(5):
                return await asyncio.gather(
                    *(c.before_request() for _ in range(8)), return_exceptions=True
                )

        results = asyncio.run(scenario())
        assert sum(result is None for result in results) == 5
        assert sum(isinstance(result, AdmissionDeferred) for result in results) == 3
        starts = [
            row[0]
            for row in c.state.db.execute("SELECT at FROM request_start ORDER BY at")
        ]
        assert all(b - a >= 0.2 - 1e-6 for a, b in pairwise(starts))
    finally:
        for collector in group:
            collector.state.close()


def test_admission_read_failure_keeps_producer_error_isolation(tmp_path, monkeypatch):
    import sqlite3

    group = collectors(tmp_path)
    events, waits = [], []
    pipeline = Pipeline(group, lambda *args: events.append(args))

    async def page(collector):
        return False

    def failed():
        raise sqlite3.OperationalError("injected admission read failure")

    async def sleep(delay):
        waits.append(delay)
        raise asyncio.CancelledError

    pipeline.page = page
    group[0].admission_delay = failed
    monkeypatch.setattr("catalog_worker.pipeline.asyncio.sleep", sleep)
    try:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(pipeline.producer(group[0], False))
        assert waits == [1]
        assert events[0][2] == "OperationalError"
    finally:
        for collector in group:
            collector.state.close()


def test_bind_host_defaults_to_loopback_and_explicit_container_bind_wins(tmp_path):
    path = tmp_path / "config.json"

    def write(host=None):
        data = {
            "providers": {"aniworld.to": "https://aniworld.to"},
            "canonical_sources": {},
            "state_dir": str(tmp_path / "state"),
            "output_dir": str(tmp_path / "read"),
            "source_id": "test",
        }
        if host is not None:
            data["bind_host"] = host
        path.write_text(json.dumps(data))

    write()
    assert load(path).bind_host == "127.0.0.1"
    write("0.0.0.0")
    assert load(path).bind_host == "0.0.0.0"
