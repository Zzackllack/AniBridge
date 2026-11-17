"""Finite publication harness control flow, separate from performance evidence."""

import json
from pathlib import Path

from catalog_worker.state import State
from catalog_worker.state_migrations import rollback_publication
from test_query import NOW


def test_benchmark_harness_runs_its_bounded_query_and_comparison_checks(tmp_path):
    """Exercise harness control flow; this uses current full export as its baseline."""
    import subprocess
    import sys

    from catalog_core import identity

    root = tmp_path / "benchmark"
    ledger = tmp_path / "ledgers"
    root.mkdir()
    ledger.mkdir()
    (root / "COPY_ONLY").touch()
    (ledger / "COPY_ONLY").touch()
    for provider in ("aniworld.to", "s.to"):
        state = State(ledger / (provider + ".sqlite"), provider)
        with state.db:
            for slug, size in (("ordinary", 5), ("large", 60)):
                path = "/series/" + slug
                tid = identity.title_id(provider, path)
                state.db.execute(
                    "INSERT INTO title VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        tid,
                        path,
                        slug,
                        slug.title(),
                        slug,
                        "series",
                        None,
                        path,
                        NOW,
                        "partial",
                    ),
                )
                for episode in range(1, size + 1):
                    anchor = path + f"/season-1/episode-{episode}"
                    eid = identity.entity_id(provider, anchor)
                    state.db.execute(
                        "INSERT INTO entity VALUES(?,?,?,?,?,?,?,?,?)",
                        (eid, tid, anchor, "episode", 1, episode, None, anchor, NOW),
                    )
                    state.db.execute(
                        "INSERT INTO release VALUES(?,?,?,?,?)",
                        (
                            identity.release_id(provider, eid, "de-dub"),
                            eid,
                            "de-dub",
                            NOW,
                            NOW,
                        ),
                    )
        state.close()
        rollback_publication(ledger / (provider + ".sqlite"), provider)
    script = (
        Path(__file__).resolve().parents[3]
        / "scripts/catalog/query_pilot/publication_benchmark.py"
    )
    for mode in ("seed", "legacy", "incremental"):
        subprocess.run(
            [
                sys.executable,
                str(script),
                mode,
                "--root",
                str(root),
                "--state",
                str(ledger),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
    result = json.loads((root / "incremental-result.json").read_text())
    assert result["provider_isolation"] == [503, 200]
    assert all(result["last_good"].values())
    assert all(
        not any(p["public_row_differences"].values())
        for p in result["comparison"].values()
    )
    assert {row["partition_episodes"] for row in result["targeted"]} == {5, 60}
    verification = script.with_name("publication_preservation.py")
    for mode in ("verify", "downgrade", "reopen", "verify"):
        subprocess.run(
            [
                sys.executable,
                str(verification),
                mode,
                "--root",
                str(root),
                "--state",
                str(ledger),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
    preserved = json.loads((root / "verify-preservation.json").read_text())
    assert all(p["initial_full_required"] for p in preserved.values())
    assert all(p["before"] == p["after"] for p in preserved.values())
