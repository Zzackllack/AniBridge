"""Damaged private caches cannot strand retries or supply accepted evidence."""

import asyncio
import hashlib
import json

import pytest
from test_matching_followup import NOW, seed

from catalog_worker import descriptors
from catalog_worker.canonical import Enricher
from catalog_worker.mapping import CanonicalEpisode
from catalog_worker.transport import Fetch


@pytest.mark.parametrize(
    "damage",
    [
        "json",
        "digest",
        "parent_id",
        "languages",
        "episodes",
        "coordinate",
        "aliases",
        "duplicate_id",
    ],
)
def test_invalid_shared_descriptor_falls_back_to_remote_without_state_loss(
    tmp_path, damage
):
    state, _ = seed(tmp_path)
    other, _ = seed(tmp_path, provider="s.to")
    response = {"tvdbId": 123, "title": "Example", "year": 2020, "episodes": []}
    with other.db:
        descriptors.save(
            other, "123", response, [CanonicalEpisode(1, 1, "One", "99")], NOW, 600
        )
        data = json.loads(
            other.db.execute("SELECT payload FROM canonical_descriptor").fetchone()[0]
        )
        if damage == "parent_id":
            data["tvdbId"] = 456
        elif damage == "languages":
            data["languages"] = [{"private": "secret"}]
        elif damage == "episodes":
            del data["episodes"]
        elif damage == "coordinate":
            data["episodes"][0]["season"] = 2**63
        elif damage == "aliases":
            data["episodes"][0]["aliases"] = None
        elif damage == "duplicate_id":
            data["episodes"].append({**data["episodes"][0], "episode": 2})
        raw = "{" if damage == "json" else json.dumps(data)
        digest = (
            "0" * 64 if damage == "digest" else hashlib.sha256(raw.encode()).hexdigest()
        )
        other.db.execute(
            "UPDATE canonical_descriptor SET payload=?,content_hash=?", (raw, digest)
        )
    before = {
        t: list(state.db.execute(f"SELECT * FROM {t}"))
        for t in ("work", "release", "canonical_title", "canonical_episode")
    }
    calls = []

    async def fetch(origin, path, **kwargs):
        calls.append(path)
        return Fetch(
            "ok", json.dumps([response] if "search" in path else response).encode()
        )

    try:
        worker = Enricher({}, fetcher=fetch, clock=lambda: NOW, states=[other, state])
        assert asyncio.run(worker.tick(state, NOW))
        assert len(calls) == 2 and worker.last_work != "descriptor_reuse"
        assert state.db.execute("SELECT failures FROM mapping_input").fetchone()[0] == 0
        for table, rows in before.items():
            assert list(state.db.execute(f"SELECT * FROM {table}")) == rows
    finally:
        state.close()
        other.close()
