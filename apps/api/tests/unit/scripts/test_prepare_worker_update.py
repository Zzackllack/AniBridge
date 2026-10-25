"""Update preparation must fail closed before producing deployable files."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]


@pytest.fixture
def update(monkeypatch):
    folder = ROOT / "scripts/catalog/query_pilot"
    monkeypatch.syspath_prepend(str(folder))
    spec = importlib.util.spec_from_file_location(
        "prepare_worker_update", folder / "prepare_worker_update.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runs(update):
    return [
        {
            "check_runs": [
                {"id": i, "name": name, "status": "completed", "conclusion": "success"}
                for i, name in enumerate(sorted(update.REQUIRED), start=10)
            ]
        }
    ]


def test_checks_require_gate_and_both_published_architectures(update):
    checks = runs(update)
    assert set(update.checked_runs(checks)) == update.REQUIRED
    checks[0]["check_runs"].pop()
    with pytest.raises(ValueError, match="missing"):
        update.checked_runs(checks)


@pytest.mark.parametrize(
    "status,conclusion",
    [("in_progress", None), ("completed", "failure"), ("completed", "skipped")],
)
def test_unfinished_or_failed_checks_block_preparation(update, status, conclusion):
    checks = runs(update)
    checks[0]["check_runs"][0].update(status=status, conclusion=conclusion)
    with pytest.raises(ValueError, match="unfinished or unsuccessful"):
        update.checked_runs(checks)


def test_latest_rerun_supersedes_failure_across_paginated_results(update):
    checks = runs(update)
    rerun = {**checks[0]["check_runs"][0], "id": 100}
    checks[0]["check_runs"][0]["conclusion"] = "failure"
    assert update.checked_runs(checks + [{"check_runs": [rerun]}])[rerun["name"]] == 100


def test_manifest_requires_digest_and_both_linux_architectures(update):
    manifest = {
        "digest": "sha256:" + "a" * 64,
        "manifests": [
            {"platform": {"os": "linux", "architecture": arch}}
            for arch in ("amd64", "arm64")
        ],
    }
    assert update.pinned_image(manifest) == update.PACKAGE + "@" + manifest["digest"]
    manifest["digest"] = "latest"
    with pytest.raises(ValueError, match="immutable"):
        update.pinned_image(manifest)
    manifest["manifests"].pop()
    with pytest.raises(ValueError, match="architectures"):
        update.pinned_image(manifest)


def test_generated_commands_refuse_an_active_project_before_any_run(update, tmp_path):
    docker = tmp_path / "docker"
    docker.write_text(
        '#!/bin/sh\nif [ "$1" = ps ]; then echo active-container; else exit 99; fi\n'
    )
    docker.chmod(0o700)
    script = tmp_path / "stopped-state.sh"
    script.write_text(
        update.stopped_commands(update.PACKAGE + "@sha256:" + "a" * 64, "b" * 40)
    )
    subprocess.run(["bash", "-n", str(script)], check=True)
    result = subprocess.run(
        ["/bin/bash", str(script), "snapshot"],
        env={"PATH": str(tmp_path) + ":/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Stop the existing Coolify service" in result.stderr


@pytest.mark.parametrize("target", ["v5", "v6"])
def test_rollback_can_read_the_private_operator_receipt(update, tmp_path, target):
    revision = "b" * 40
    invocation = tmp_path / "invocation.json"
    docker = tmp_path / "docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        "import json,sys\n"
        "from pathlib import Path\n"
        "if sys.argv[1:3] == ['image','inspect']:\n"
        f"    print({revision!r})\n"
        "elif sys.argv[1] == 'run':\n"
        f"    Path({str(invocation)!r}).write_text(json.dumps(sys.argv[2:]))\n"
    )
    docker.chmod(0o700)
    script = tmp_path / "stopped-state.sh"
    script.write_text(
        update.stopped_commands(update.PACKAGE + "@sha256:" + "a" * 64, revision)
    )
    (tmp_path / "baseline.json").write_text("{}")
    result = subprocess.run(
        ["/bin/bash", str(script), "rollback-" + target],
        env={"PATH": str(tmp_path) + ":/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    args = json.loads(invocation.read_text())
    # Operator directories/receipts are private and may belong to another UID.
    # Snapshot/verify already run as root; rollback needs the same read access.
    assert "--user" in args and args[args.index("--user") + 1] == "0"
    assert "ROLLBACK_VERSION=" + target[1:] in args
