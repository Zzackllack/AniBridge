"""A cached correspondence result must not consume an expired remote retry."""

import asyncio
import json

import pytest
from catalog_worker import canonical_cache, descriptors
from catalog_worker.canonical import Enricher
from catalog_worker.transport import Fetch
from test_canonical import NOW, ready
from test_matching_followup import seed


@pytest.mark.parametrize("recovered", [False, True])
def test_due_failure_with_cached_names_retries_and_leaves_queue(tmp_path, recovered):
    state = ready(tmp_path)
    calls = []
    response = {"tvdbId": 123, "title": "Example", "year": 2020, "episodes": []}
    clock = [NOW]

    async def fetch(origin, path, **kwargs):
        calls.append(path)
        if clock[0] > NOW and not recovered:
            return Fetch("http_error", status=500)
        return Fetch(
            "ok", json.dumps([response] if "search" in path else response).encode()
        )

    worker = Enricher({}, fetcher=fetch, clock=lambda: clock[0])
    assert asyncio.run(worker.tick(state, NOW))
    with state.db:
        # A later failed lookup can coexist with earlier usable cached names.
        # Keep its retry history, including while the matcher version changes.
        state.db.execute(
            "UPDATE mapping_input SET failures=1,outcome='source_failure',"
            "checked_at=?,next_due=?,matcher='old'",
            (NOW + 1, NOW + 301),
        )
    before = {
        table: list(state.db.execute(f"SELECT * FROM {table}"))
        for table in ("canonical_episode", "canonical_cache", "work", "release")
    }
    calls.clear()
    assert not asyncio.run(worker.tick(state, NOW + 300))
    assert not calls
    clock[0] = NOW + 301
    # A restart must neither lose the deadline nor strand this retry behind cache.
    worker = Enricher({}, fetcher=fetch, clock=lambda: clock[0])
    assert asyncio.run(worker.tick(state, clock[0]))
    assert len(calls) == 1
    row = state.db.execute("SELECT * FROM mapping_input").fetchone()
    assert row["failures"] == (0 if recovered else 2)
    assert row["outcome"] == ("unchanged" if recovered else "source_failure")
    assert row["next_due"] > clock[0]
    if not recovered:
        assert row["next_due"] == clock[0] + 1800
    calls.clear()
    assert not asyncio.run(worker.tick(state, clock[0] + 1))
    assert not calls
    for table, rows in before.items():
        if recovered and table == "canonical_cache":
            continue  # A successful descriptor lookup advances only its clock.
        assert list(state.db.execute(f"SELECT * FROM {table}")) == rows
    state.close()


def test_retry_can_recover_from_newer_verified_cross_provider_descriptor(tmp_path):
    state = ready(tmp_path)
    other, _ = seed(tmp_path, provider="s.to")
    response = {"tvdbId": 123, "title": "Example", "year": 2020, "episodes": []}
    calls = []

    async def fetch(origin, path, **kwargs):
        calls.append(path)
        return Fetch(
            "ok", json.dumps([response] if "search" in path else response).encode()
        )

    worker = Enricher({}, fetcher=fetch, clock=lambda: NOW)
    assert asyncio.run(worker.tick(state, NOW))
    with state.db:
        state.db.execute(
            "UPDATE mapping_input SET failures=1,outcome='source_failure',checked_at=?,next_due=?",
            (NOW + 1, NOW + 301),
        )
    with other.db:
        descriptors.save(other, "123", response, [], NOW + 2, canonical_cache.TTL)
    calls.clear()
    worker = Enricher({}, fetcher=fetch, clock=lambda: NOW + 301, states=[state, other])
    assert asyncio.run(worker.tick(state, NOW + 301))
    assert worker.last_work == "descriptor_reuse" and not calls
    row = state.db.execute("SELECT * FROM mapping_input").fetchone()
    assert row["failures"] == 0 and row["next_due"] > NOW + 301
    assert not asyncio.run(worker.tick(state, NOW + 302))
    state.close()
    other.close()
