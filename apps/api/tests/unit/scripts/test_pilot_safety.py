"""Destructive fixture hooks and recovery plans must fail before mutation."""

import importlib.util
import json
import stat
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[5]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts/catalog/query_pilot" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "test_mode,source,origin",
    [
        ("", "private-fixture", "https://fixture.invalid"),
        ("1", "operator-source", "https://fixture.invalid"),
        ("1", "private-fixture", "https://real-provider.example"),
    ],
)
def test_outage_hook_refuses_non_fixture_before_opening_cache(
    monkeypatch, tmp_path, test_mode, source, origin
):
    outage = load_script("outage")
    path = tmp_path / "worker.json"
    path.write_text(json.dumps({"source_id": source, "providers": {"s.to": origin}}))
    monkeypatch.setenv("ANIBRIDGE_TEST_MODE", test_mode)
    monkeypatch.setattr(outage, "Path", lambda _: path)

    def unexpected_cache(*args, **kwargs):
        pytest.fail("non-fixture outage probe opened a cache")

    monkeypatch.setattr(outage.sqlite3, "connect", unexpected_cache)
    with pytest.raises(RuntimeError, match="fixture"):
        outage.main()


def test_outage_guard_accepts_the_generated_fixture(tmp_path):
    outage = load_script("outage")
    path = tmp_path / "worker.json"
    path.write_text(
        json.dumps(
            {
                "source_id": "private-fixture",
                "providers": {"aniworld.to": "https://fixture.invalid"},
            }
        )
    )
    outage.require_fixture({"ANIBRIDGE_TEST_MODE": "1"}, path)


def test_pilot_metadata_reader_has_no_private_ledger_mount():
    folder = ROOT / "scripts/catalog/query_pilot"
    compose = yaml.safe_load((folder / "compose.yaml").read_text())
    reader = compose["services"]["catalog"]
    assert "--serve" in reader["command"]
    assert {mount.split(":")[0] for mount in reader["volumes"]} == {
        "config",
        "read-catalog",
    }
    # The real-provider overlay must inherit the same reader boundary.
    show = yaml.safe_load((folder / "show.yaml").read_text())
    assert "volumes" not in show["services"].get("catalog", {})


def test_private_recovery_output_is_exclusive_and_restrictive(tmp_path):
    script = load_script("stage_registry_upgrade")
    path = tmp_path / "rollback.json"
    script.write_private(path, '{"original":true}\n')
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        script.write_private(path, "replacement")
    assert path.read_text() == '{"original":true}\n'
    assert list(tmp_path.iterdir()) == [path]


def test_interrupted_private_write_never_publishes_partial_recovery(
    monkeypatch, tmp_path
):
    script = load_script("stage_registry_upgrade")
    path = tmp_path / "candidate.json"

    def interrupted_flush(descriptor):
        assert not path.exists()
        raise OSError("simulated failed file fsync")

    monkeypatch.setattr(script.os, "fsync", interrupted_flush)
    with pytest.raises(OSError, match="simulated"):
        script.write_private(path, "private recovery data")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("service_id", ["../other", "x; true", "$(command)", ""])
def test_operator_project_identifiers_cannot_change_shell_arguments(service_id):
    script = load_script("stage_registry_upgrade")
    with pytest.raises(ValueError, match="service ID"):
        script.require_service_id(service_id)
