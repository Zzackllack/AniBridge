"""Exercise the offline replay's copy guard, retry progress and preservation."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from catalog_worker.canonical import Enricher
from catalog_worker.transport import Fetch
from test_canonical import NOW, ready
from test_matching_followup import seed


def test_retry_replay_advances_without_clearing_failures_or_touching_baseline(tmp_path):
    root = tmp_path / "replay"
    baseline = root / "baseline"
    baseline.mkdir(parents=True)
    state = ready(baseline)
    state.close()
    # ready() uses worker.sqlite; the replay requires explicit provider filenames.
    (baseline / "worker.sqlite").rename(baseline / "aniworld.to.sqlite")
    state, _ = seed(baseline, provider="s.to", mapped=False)

    async def fetch(origin, path, **kwargs):
        item = {
            "tvdbId": 123,
            "title": "Example",
            "year": 2020,
            "episodes": [],
            "metadataSource": "tvdb",
            "language": "deu" if "/deu/" in path else "eng",
        }
        return Fetch("ok", json.dumps([item] if "search" in path else item).encode())

    worker = Enricher(
        {"tv": "skyhook", "movie": "off", "episode_languages": ["deu"]},
        fetcher=fetch,
        clock=lambda: NOW,
    )
    assert asyncio.run(worker.tick(state, NOW))
    with state.db:
        state.db.execute(
            "UPDATE mapping_input SET failures=1,outcome='source_failure',checked_at=?,next_due=?",
            (NOW + 1, NOW + 301),
        )
    state.close()
    script = (
        Path(__file__).resolve().parents[3]
        / "scripts/catalog/query_pilot/cached_retry_replay.py"
    )
    command = [
        sys.executable,
        str(script),
        str(root),
        "--phase",
        "after",
        "--now",
        str(NOW + 301),
        "--ticks",
        "2",
    ]
    rejected = subprocess.run(command, check=False, capture_output=True, timeout=30)
    assert rejected.returncode != 0 and not (root / "after").exists()
    (baseline / "COPY_ONLY").touch()
    subprocess.run(command, check=True, capture_output=True, timeout=30)
    result = json.loads((root / "after.json").read_text())["providers"]["s.to"]
    assert result["simulated_requests"] == result["distinct_lookup_attempts"] == 1
    assert result["before"]["queue"]["failed_due"] == 1
    assert result["after"]["queue"]["failed_due"] == 0
    assert result["outcomes"] == {"source_failure": 1, "idle": 1}
    assert not any(row["old_rows_changed"] for row in result["preservation"].values())
    # Refuse to reuse a candidate directory rather than silently resetting it.
    assert (
        subprocess.run(command, check=False, capture_output=True, timeout=30).returncode
        != 0
    )
