"""Prepare a tested, pinned worker update; never write to Coolify or deploy."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from stage_registry_upgrade import SERVICE, prepare, write_private

PACKAGE = "ghcr.io/zzackllack/anibridge-catalog-worker-preview"
REPOSITORY = "Zzackllack/AniBridge"
REQUIRED = {
    "Tests / Required Gate",
    "Build catalog-worker (amd64)",
    "Build catalog-worker (arm64)",
    "Publish catalog-worker manifest",
}


def checked_runs(pages: list[dict]) -> dict[str, int]:
    # A rerun supersedes an older failed attempt with the same check name.
    latest = {}
    for page in pages:
        for run in page["check_runs"]:
            if run["id"] > latest.get(run["name"], {}).get("id", -1):
                latest[run["name"]] = run
    if not REQUIRED <= latest.keys():
        raise ValueError("required test/image checks are missing at this revision")
    if any(
        run["status"] != "completed" or run["conclusion"] != "success"
        for run in latest.values()
    ):
        raise ValueError("revision has unfinished or unsuccessful checks")
    return {name: latest[name]["id"] for name in sorted(latest)}


def pinned_image(manifest: dict) -> str:
    platforms = {
        (row.get("platform", {}).get("os"), row.get("platform", {}).get("architecture"))
        for row in manifest.get("manifests", [])
    }
    if not {("linux", "amd64"), ("linux", "arm64")} <= platforms:
        raise ValueError("both native worker architectures are required")
    digest = manifest.get("digest", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("registry did not return an immutable manifest digest")
    return PACKAGE + "@" + digest


def output(argv: list[str]) -> str:
    return subprocess.run(
        argv, check=True, capture_output=True, text=True, timeout=120
    ).stdout


def stopped_commands(image: str, revision: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
test -z "$(docker ps --filter label=com.docker.compose.project={SERVICE} -q)" || {{
  echo 'Stop the existing Coolify service in Zen first, without Docker Cleanup.' >&2
  exit 1
}}
IMAGE={image}
test "$(docker image inspect "$IMAGE" --format '{{{{index .Config.Labels "org.opencontainers.image.revision"}}}}')" = {revision}
COMMON=(--rm --network none --cpus 2 --memory 2g --memory-swap 2g --pids-limit 96
  -v {SERVICE}_config:/config:ro
  -v {SERVICE}_worker-state:/state
  -v {SERVICE}_read-catalog:/read
  -v "$PWD:/plan")
case "${{1:-}}" in
  snapshot|verify)
    docker run "${{COMMON[@]}}" --user 0 --entrypoint python "$IMAGE" /plan/verify_worker_update.py "$1" "${{@:2}}"
    ;;
  publish)
    test -f baseline.json
    docker run "${{COMMON[@]}}" "$IMAGE" --config /config/worker.json --publish
    ;;
  rollback-v5)
    test -f baseline.json
    docker run -i "${{COMMON[@]}}" --entrypoint python "$IMAGE" - <<'PY'
from catalog_worker.config import load
from catalog_worker.state_migrations import preflight, rollback_publication
import json
from pathlib import Path
baseline = json.loads(Path('/plan/baseline.json').read_text())
assert all(row['version'] == 5 for row in baseline.values()), 'Only a v5 baseline permits v6-to-v5 rollback'
config = load(Path('/config/worker.json'))
for provider in config.providers:
    path = config.state_dir / (provider + '.sqlite')
    if preflight(path, provider) == 6:
        rollback_publication(path, provider)
    assert preflight(path, provider) == 5
print('Private state v5 retained; restore rollback.yaml in Zen before starting.')
PY
    ;;
  *) echo 'Usage: bash stopped-state.sh snapshot|publish|verify|rollback-v5' >&2; exit 2 ;;
esac
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--compose", type=Path, required=True)
    parser.add_argument("--worker-config", type=Path, required=True)
    parser.add_argument("--expected-old-image", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        parser.error("use the full reviewed source commit, not a branch or latest")
    if args.directory.exists():
        parser.error("use a new directory; an earlier rollback must not be replaced")
    checks = checked_runs(
        json.loads(
            output(
                [
                    "gh",
                    "api",
                    "--paginate",
                    "--slurp",
                    f"repos/{REPOSITORY}/commits/{args.revision}/check-runs?per_page=100",
                ]
            )
        )
    )
    image = pinned_image(
        json.loads(
            output(
                [
                    "docker",
                    "buildx",
                    "imagetools",
                    "inspect",
                    PACKAGE + ":sha-" + args.revision,
                    "--format",
                    "{{json .Manifest}}",
                ]
            )
        )
    )
    original = args.compose.read_text()
    original_worker = args.worker_config.read_bytes()
    candidate, rollback, worker, _ = prepare(
        {"uuid": SERVICE, "docker_compose_raw": original},
        json.loads(original_worker),
        image,
        expected_old_image=args.expected_old_image,
        preserve_worker_config=True,
    )
    assert worker == json.loads(original_worker)
    args.directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    for filename, body in (
        ("candidate.yaml", candidate),
        ("rollback.yaml", rollback),
        ("worker-original.json", original_worker.decode()),
        (
            "verify_worker_update.py",
            Path(__file__).with_name("verify_worker_update.py").read_text(),
        ),
        ("stopped-state.sh", stopped_commands(image, args.revision)),
    ):
        write_private(args.directory / filename, body)
    receipt = {
        "revision": args.revision,
        "image": image,
        "old_image": args.expected_old_image,
        "service": SERVICE,
        "checks": checks,
        "original_compose_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "original_worker_sha256": hashlib.sha256(original_worker).hexdigest(),
        "deployment": "not_started",
    }
    write_private(args.directory / "plan.json", json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps(
            {
                "directory": str(args.directory),
                "image": image,
                "deployment": "not_started",
            }
        )
    )


if __name__ == "__main__":
    main()
