"""Offline setup and stopped-ledger helpers; no deployment or live crawl."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from catalog_core import release_metadata
from catalog_core.providers.aniworld import Link, Page

from catalog_worker.config import load
from catalog_worker.state import State
from catalog_worker.state_migrations import preflight

ROOT = Path(__file__).resolve().parents[3]


def module(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def prepare(monkeypatch, path: Path, *args: str) -> dict:
    script = module(
        "scripts/catalog/query_pilot/prepare_server.py", "prepare_server_test"
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_server.py",
            str(path),
            "--metadata-origin",
            "https://metadata.example",
            *args,
        ],
    )
    script.main()
    return json.loads((path / "worker.json").read_text())


def filmo_worker_state(state_dir: Path) -> None:
    state = State(state_dir / "filmo.to.sqlite", "filmo.to")
    now = 1_800_000_000
    path = "/movies/example"
    state.listing(Page((Link(path, "Poster Name"),), (), 0, None), now)
    offer = release_metadata.validate(
        {
            "variant_anchor": "817:provider-row",
            "native_id": "817",
            "host": "VOE",
            "language_label": "Deutsch Dub",
            "audio_languages": ["deu"],
            "subtitle_languages": None,
            "audio_role": "dubbed",
            "subtitle_mode": "unknown",
            "quality": {"labels": ["1080p"], "source": "web", "resolution": 1080},
        }
    )
    state.detail(
        state.claim(now),
        Page((), (), 0, "Detailed Name", offers=(offer,)),
        now,
    )
    state.close()


def test_prepare_server_keeps_defaults_and_only_adds_filmo_when_requested(
    tmp_path, monkeypatch, capsys
):
    default_dir = tmp_path / "defaults"
    worker = prepare(monkeypatch, default_dir)
    assert worker["providers"] == {
        "aniworld.to": "https://aniworld.to",
        "s.to": "https://serienstream.to",
    }
    assert worker["canonical_sources"]["movie"] == "off"

    filmo_dir = tmp_path / "with-filmo"
    worker = prepare(
        monkeypatch,
        filmo_dir,
        "--filmo-origin",
        "https://movies.example",
        "--megakino-origin",
        "https://megakino.example",
    )
    assert len(worker["providers"]) == 4
    assert worker["providers"]["filmo.to"] == "https://movies.example"
    assert (
        load(filmo_dir / "worker.json").providers.keys() == worker["providers"].keys()
    )
    assert worker["canonical_sources"]["movie"] == "off"
    message = capsys.readouterr().out
    assert "canonical_sources.movie to radarr" in message
    assert "tmdb with a private token" in message


def test_prepare_server_rejects_invalid_origin_and_never_replaces_credentials(
    tmp_path, monkeypatch
):
    script = module(
        "scripts/catalog/query_pilot/prepare_server.py", "prepare_server_invalid_test"
    )
    invalid_dir = tmp_path / "invalid"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_server.py",
            str(invalid_dir),
            "--metadata-origin",
            "https://metadata.example",
            "--filmo-origin",
            "http://filmo.example",
        ],
    )
    with pytest.raises(SystemExit):
        script.main()
    assert not invalid_dir.exists() or not list(invalid_dir.iterdir())

    protected = tmp_path / "protected"
    protected.mkdir()
    token = protected / "metadata-token"
    token.write_text("operator-secret\n")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_server.py",
            str(protected),
            "--metadata-origin",
            "https://metadata.example",
            "--filmo-origin",
            "https://filmo.example",
        ],
    )
    with pytest.raises(SystemExit):
        script.main()
    assert token.read_text() == "operator-secret\n"


def test_worker_update_version_policy_is_provider_scoped():
    script = module(
        "scripts/catalog/query_pilot/verify_worker_update.py",
        "verify_worker_update_versions_test",
    )
    assert script.supported_state_versions("filmo.to") == {8}
    assert script.supported_state_versions("aniworld.to") == {5, 6, 7}
    assert script.supported_state_versions("megakino") == {5, 6, 7}


def test_filmo_v8_snapshot_verify_preserves_offer_and_rejects_mutation(tmp_path):
    script = module(
        "scripts/catalog/query_pilot/verify_worker_update.py",
        "verify_worker_update_filmo_test",
    )
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    config = {
        "providers": {
            "aniworld.to": "https://aniworld.to",
            "filmo.to": "https://filmo.to",
        },
        "canonical_sources": {"tv": "off", "movie": "off"},
        "state_dir": str(state_dir),
        "output_dir": str(tmp_path / "read"),
        "source_id": "snapshot-test",
    }
    config_path = tmp_path / "worker.json"
    encoded = json.dumps(config, sort_keys=True).encode() + b"\n"
    config_path.write_bytes(encoded)
    filmo_worker_state(state_dir)
    State(state_dir / "aniworld.to.sqlite", "aniworld.to").close()
    with pytest.raises(
        ValueError,
        match="variant state requires Filmo|unsupported worker table contract|wrong worker state",
    ):
        preflight(state_dir / "filmo.to.sqlite", "aniworld.to")
    plan = tmp_path / "plan"
    plan.mkdir()
    (plan / "plan.json").write_text(
        json.dumps({"original_worker_sha256": hashlib.sha256(encoded).hexdigest()})
    )

    snapshot = script.run("snapshot", config_path, plan)
    assert snapshot == {"aniworld.to": "snapshotted", "filmo.to": "snapshotted"}
    receipt = json.loads((plan / "baseline.json").read_text())
    assert receipt["filmo.to"]["version"] == 8
    assert receipt["aniworld.to"]["version"] == 7
    verified = script.run("verify", config_path, plan)
    assert verified["filmo.to"]["release_metadata"]["old_rows_missing_or_changed"] == 0

    filename = state_dir / "filmo.to.sqlite"
    state = State(filename, "filmo.to")
    metadata_json = state.db.execute(
        "SELECT metadata_json FROM release_metadata"
    ).fetchone()[0]
    metadata = json.loads(metadata_json)
    metadata["quality"]["resolution"] = 720
    state.db.execute(
        "UPDATE release_metadata SET metadata_json=?", (json.dumps(metadata),)
    )
    state.db.commit()
    state.close()
    with pytest.raises(
        ValueError, match="stopped-state preservation failed: release_metadata"
    ):
        script.run("verify", config_path, plan)
