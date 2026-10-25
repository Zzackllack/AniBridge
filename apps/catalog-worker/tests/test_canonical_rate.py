"""A configurable shared budget changes admission, never matching evidence."""

import asyncio
import importlib.util
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest
from catalog_core.providers.transport import AdmissionDeferred, Fetch
from test_canonical import NOW, ready

from catalog_worker.canonical import Enricher
from catalog_worker.config import load
from catalog_worker.events import Events
from catalog_worker.state import State


@pytest.mark.parametrize("rate", [4, 30, 60, 90, 120])
def test_shared_budget_survives_restart_and_expires(tmp_path, rate):
    paths = [tmp_path / "a.sqlite", tmp_path / "b.sqlite"]
    providers = ["aniworld.to", "s.to"]
    states = [State(path, provider) for path, provider in zip(paths, providers)]
    clock = [NOW]
    enricher = Enricher(
        {}, states=states, requests_per_minute=rate, clock=lambda: clock[0]
    )
    for i in range(rate):
        enricher.current_state = states[i % 2]
        enricher.admit_request()
    with pytest.raises(AdmissionDeferred):
        enricher.admit_request()
    for state in states:
        state.close()
    states = [State(path, provider) for path, provider in zip(paths, providers)]
    restarted = Enricher(
        {}, states=states, requests_per_minute=rate, clock=lambda: clock[0]
    )
    assert restarted.request_count(NOW) == rate
    with pytest.raises(AdmissionDeferred):
        restarted.admit_request()
    clock[0] += 60
    restarted.current_state = states[0]
    restarted.admit_request()
    assert restarted.request_count(clock[0]) == 1
    for state in states:
        state.close()


def test_lowering_limit_honors_previous_larger_window(tmp_path):
    state = ready(tmp_path)
    with state.db:
        state.db.executemany(
            "INSERT INTO canonical_request_start VALUES(?)", [(NOW,)] * 60
        )
    reduced = Enricher({}, states=[state], requests_per_minute=30, clock=lambda: NOW)
    with pytest.raises(AdmissionDeferred):
        reduced.admit_request()
    assert reduced.request_count(NOW) == 60
    state.close()


def test_rate_change_does_not_invalidate_verified_cache_or_rematch(tmp_path):
    state = ready(tmp_path)
    calls = []

    async def fetch(origin, path, **kwargs):
        calls.append(path)
        item = {"tvdbId": 123, "title": "Example", "year": 2020, "episodes": []}
        return Fetch("ok", json.dumps([item] if "search" in path else item).encode())

    original = Enricher({}, fetcher=fetch, requests_per_minute=30)
    assert asyncio.run(original.tick(state, NOW))
    before = dict(state.db.execute("SELECT * FROM mapping_input").fetchone())
    replay = dict(state.db.execute("SELECT * FROM matching_replay").fetchone())
    faster = Enricher({}, fetcher=fetch, requests_per_minute=90)
    assert faster.matcher == original.matcher
    assert not asyncio.run(faster.tick(state, NOW + 1))
    assert len(calls) == 2
    assert dict(state.db.execute("SELECT * FROM mapping_input").fetchone()) == before
    assert dict(state.db.execute("SELECT * FROM matching_replay").fetchone()) == replay
    state.close()


@pytest.mark.parametrize("value", [True, 0, 3, 121, "60", 60.0])
def test_invalid_rate_rejected_by_config_and_enricher(tmp_path, value):
    config = {
        "providers": {"aniworld.to": "https://aniworld.to"},
        "canonical_sources": {},
        "state_dir": str(tmp_path / "state"),
        "output_dir": str(tmp_path / "read"),
        "source_id": "rate-test",
        "limits": {"canonical_requests_per_minute": value},
    }
    filename = tmp_path / "config.json"
    filename.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        load(filename)
    with pytest.raises(ValueError):
        Enricher({}, requests_per_minute=value)


def test_canonical_metrics_are_bounded_and_do_not_expose_response(tmp_path):
    events = Events(tmp_path)
    events.canonical(
        "s.to",
        Fetch(
            "rate_limited",
            b"private HTML /player?token=secret",
            status=429,
            retry_after=120,
            error_class="private error",
            requests=2,
            duration_s=0.25,
        ),
    )
    events.canonical("aniworld.to", Fetch("private query term", b"credentials"))
    events.close()
    text = (tmp_path / "worker.jsonl").read_text()
    rows = [json.loads(line) for line in text.splitlines()]
    assert rows[0]["http_status"] == 429 and rows[0]["retry_after_s"] == 120
    assert rows[0]["requests"] == 2 and rows[0]["network_s"] == 0.25
    assert rows[1]["outcome"] == "rejected"
    assert not any(
        word in text for word in ("private", "player", "token", "credentials")
    )


def test_fetch_observer_sees_failure_before_title_retry(tmp_path):
    state = ready(tmp_path)
    reports = []

    async def fetch(*args, **kwargs):
        return Fetch("rate_limited", retry_after=600, status=429, requests=1)

    enricher = Enricher({}, fetcher=fetch, on_fetch=lambda p, r: reports.append((p, r)))
    assert asyncio.run(enricher.tick(state, NOW))
    row = state.db.execute("SELECT * FROM mapping_input").fetchone()
    assert row["next_due"] == NOW + 600 and row["failures"] == 1
    assert reports[0][0] == "aniworld.to" and reports[0][1].status == 429
    state.close()


@pytest.fixture
def rate_probe(monkeypatch):
    scripts = Path(__file__).resolve().parents[3] / "scripts/catalog/query_pilot"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "rate_probe", scripts / "canonical_rate_probe.py"
    )
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    return probe


def test_probe_stops_escalation_on_throttling_and_preserves_copied_work(
    tmp_path, monkeypatch, rate_probe
):
    probe = rate_probe
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    (baseline / "COPY_ONLY").touch()
    first = ready(tmp_path / "seed")
    with closing(sqlite3.connect(baseline / "aniworld.to.sqlite")) as target:
        first.db.backup(target)
    first.close()
    State(baseline / "s.to.sqlite", "s.to").close()
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "COPY_ONLY").touch()

    class Throttled:
        def __init__(self, *args):
            pass

        async def fetch(self, origin, path, **options):
            await options["before_request"]()
            return Fetch("rate_limited", status=429, retry_after=120, requests=1)

        async def close(self):
            pass

    monkeypatch.setattr(probe, "Session", Throttled)
    args = SimpleNamespace(
        baseline=baseline,
        candidate=candidate,
        sources={},
        seconds=60,
        rates=[30, 60],
        output=candidate / "result.json",
    )
    asyncio.run(probe.run(args))
    steps = json.loads(args.output.read_text())["steps"]
    assert len(steps) == 1 and steps[0]["stop_reason"] == "rate_limited"
    assert steps[0]["requests"] == 1 and steps[0]["statuses"] == {"429": 1}
    for provider in ("aniworld.to", "s.to"):
        assert not any(steps[0]["after"][provider]["preservation"].values())


def test_eligibility_includes_episode_replay_and_does_not_guess_its_age(
    tmp_path, rate_probe
):
    state = ready(tmp_path)

    async def fetch(origin, path, **kwargs):
        item = {"tvdbId": 123, "title": "Example", "year": 2020, "episodes": []}
        return Fetch("ok", json.dumps([item] if "search" in path else item).encode())

    enricher = Enricher({}, fetcher=fetch)
    assert asyncio.run(enricher.tick(state, NOW))
    assert rate_probe.eligible(state, enricher, NOW)["parents"] == 0
    with state.db:
        state.db.execute("DELETE FROM matching_replay")
    assert rate_probe.eligible(state, enricher, NOW) == {
        "parents": 1,
        "oldest_due_age_s": None,
        "unknown_eligibility_age": 1,
    }
    with state.db:
        state.db.execute("UPDATE mapping_input SET next_due=?", (NOW - 20,))
    assert rate_probe.eligible(state, enricher, NOW) == {
        "parents": 1,
        "oldest_due_age_s": 20,
        "unknown_eligibility_age": 0,
    }
    state.close()
