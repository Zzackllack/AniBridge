"""Snapshot accounting must partition gaps without modifying or opening live WAL."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from test_matching_followup import NOW, episode, seed


def test_snapshot_partition_is_read_only_and_refuses_live_wal(tmp_path):
    for provider in ("aniworld.to", "s.to"):
        state, tid = seed(tmp_path, provider)
        episode(state, tid, 1, 1, "Missing canonical evidence")
        with state.db:
            state.db.execute("UPDATE mapping_input SET checked_at=?", (NOW,))
        state.close()
    script = (
        Path(__file__).resolve().parents[3]
        / "scripts/catalog/query_pilot/audit_snapshot.py"
    )
    command = [sys.executable, str(script), "--root", str(tmp_path), "--now", str(NOW)]
    rejected = subprocess.run(command, capture_output=True, check=False, timeout=30)
    assert rejected.returncode != 0
    (tmp_path / "COPY_ONLY").touch()
    before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in tmp_path.glob("*.sqlite")
    }
    result = subprocess.run(command, capture_output=True, check=True, timeout=30)
    for row in json.loads(result.stdout)["providers"].values():
        assert row["totals"]["usable_episodes"] == 1
        assert row["totals"]["unresolved_usable_episodes"] == 1
        assert row["unresolved_usable_partition"] == {"waiting_descriptor": 1}
    assert before == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in tmp_path.glob("*.sqlite")
    }
    (tmp_path / "s.to.sqlite-wal").touch()
    assert (
        subprocess.run(command, capture_output=True, check=False, timeout=30).returncode
        != 0
    )
