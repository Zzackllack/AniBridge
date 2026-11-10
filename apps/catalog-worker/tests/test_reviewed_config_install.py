"""Initializer and volume updates must retain exact originals for rollback."""

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "scripts/catalog/query_pilot/install_reviewed_worker_config.py"
)
SPEC = importlib.util.spec_from_file_location("reviewed_config_install", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def plan(tmp_path):
    operator, config, review = (tmp_path / p for p in ("operator", "config", "plan"))
    for directory in (operator, config, review):
        directory.mkdir()
    for directory, name, data in (
        (operator, "operator-rollback.json", b'{"original": true}\n'),
        (config, "volume-rollback.json", b'{ "original": true }\n'),
    ):
        (directory / "worker.json").write_bytes(data)
        (directory / "metadata-token").write_bytes(b"retained-private-fixture")
        (review / name).write_bytes(data)
    (review / "worker-candidate.json").write_bytes(b'{"candidate": true}\n')
    return operator, config, review


def test_upgrade_then_initializer_copy_then_exact_rollback(tmp_path):
    operator, config, review = plan(tmp_path)
    owners = [(p / "worker.json").stat().st_uid for p in (operator, config)]
    MODULE.install(review, operator, config)
    assert (operator / "worker.json").read_bytes() == (
        review / "worker-candidate.json"
    ).read_bytes()
    (config / "worker.json").write_bytes((operator / "worker.json").read_bytes())
    MODULE.install(review, operator, config, rollback=True)
    for index, (directory, saved) in enumerate(
        ((operator, "operator-rollback.json"), (config, "volume-rollback.json"))
    ):
        target = directory / "worker.json"
        assert target.read_bytes() == (review / saved).read_bytes()
        assert target.stat().st_uid == owners[index]
        assert target.stat().st_mode & 0o777 == 0o600
        assert (
            directory / "metadata-token"
        ).read_bytes() == b"retained-private-fixture"


@pytest.mark.parametrize("rollback", [False, True])
def test_independent_operator_edit_vetoes_both_writes(tmp_path, rollback):
    operator, config, review = plan(tmp_path)
    if rollback:
        MODULE.install(review, operator, config)
    (operator / "worker.json").write_bytes(b"independent edit")
    untouched = (config / "worker.json").read_bytes()
    with pytest.raises(ValueError, match="changed since review"):
        MODULE.install(review, operator, config, rollback=rollback)
    assert (operator / "worker.json").read_bytes() == b"independent edit"
    assert (config / "worker.json").read_bytes() == untouched


def test_second_write_failure_keeps_both_versions_recoverable(tmp_path, monkeypatch):
    operator, config, review = plan(tmp_path)
    atomic_write = MODULE.atomic_write

    def fail_volume(path, data):
        if path == config / "worker.json":
            raise OSError("fixture write failure")
        atomic_write(path, data)

    monkeypatch.setattr(MODULE, "atomic_write", fail_volume)
    with pytest.raises(OSError, match="fixture write failure"):
        MODULE.install(review, operator, config)
    monkeypatch.setattr(MODULE, "atomic_write", atomic_write)
    MODULE.install(review, operator, config, rollback=True)
    assert (operator / "worker.json").read_bytes() == (
        review / "operator-rollback.json"
    ).read_bytes()
    assert (config / "worker.json").read_bytes() == (
        review / "volume-rollback.json"
    ).read_bytes()
