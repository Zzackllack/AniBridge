"""Prepare private review files only. Coolify writes require the approved Zen UI."""

import argparse
import copy
import json
import re
from pathlib import Path

import yaml

SERVICE = "ev7cds2lpqyvqfxpcm4wp4tc"
OLD_WORKER = "ghcr.io/zzackllack/anibridge-catalog-worker-preview@sha256:1277d1fd6ec7130a53c5ed4a694dd8efada7e95db6c86bd897e3e446f2149e0a"


def prepare(
    service: dict,
    worker: dict,
    image: str,
    *,
    expected_old_image: str = OLD_WORKER,
    canonical_requests_per_minute: int | None = None,
) -> tuple[str, str, dict, dict]:
    pattern = (
        r"ghcr\.io/zzackllack/anibridge-catalog-worker-preview@sha256:[0-9a-f]{64}"
    )
    if not all(re.fullmatch(pattern, ref) for ref in (image, expected_old_image)):
        raise ValueError("pinned worker manifest required")
    if image == expected_old_image:
        raise ValueError("configuration requires the tested new worker")
    record = service.get("data", service)
    if record.get("uuid") != SERVICE:
        raise ValueError("wrong service")
    source = record["docker_compose_raw"]
    before = yaml.safe_load(source)
    after = copy.deepcopy(before)
    selected = after["services"]
    for name in ("initialize", "collector", "metadata"):
        if (
            selected[name]["image"] != expected_old_image
            or selected[name].get("pull_policy") != "missing"
        ):
            raise ValueError("live image/pull policy changed; reverify before staging")
        selected[name]["image"] = image
    for name, memory in [("collector", "2g"), ("metadata", "512m")]:
        if (
            selected[name].get("cpus") != 2
            or selected[name].get("mem_limit") != memory
            or selected[name].get("memswap_limit") != memory
        ):
            raise ValueError("unexpected resource profile")
    # The checked-in server template has a shared anchor. Only its image mirrors
    # the three concrete services; every other field must compare equal.
    anchor = after.get("x-worker")
    if anchor and anchor.get("image") == expected_old_image:
        anchor["image"] = image
    restored = copy.deepcopy(after)
    for name in ("initialize", "collector", "metadata"):
        restored["services"][name]["image"] = expected_old_image
    if anchor and anchor.get("image") == image:
        restored["x-worker"]["image"] = expected_old_image
    if restored != before:
        raise ValueError("unexpected compose mutation")
    candidate = copy.deepcopy(worker)
    languages = candidate["canonical_sources"].get("episode_languages", [])
    if languages not in ([], ["deu"]):
        raise ValueError("unexpected language configuration")
    candidate["canonical_sources"]["episode_languages"] = ["deu"]
    if canonical_requests_per_minute is not None:
        if (
            type(canonical_requests_per_minute) is not int
            or not 4 <= canonical_requests_per_minute <= 120
        ):
            raise ValueError("invalid canonical admission budget")
        candidate.setdefault("limits", {})["canonical_requests_per_minute"] = (
            canonical_requests_per_minute
        )
    return (
        yaml.safe_dump(after, sort_keys=False),
        source,
        candidate,
        copy.deepcopy(worker),
    )


def write_private(path: Path, text: str) -> None:
    with path.open("x") as stream:
        path.chmod(0o600)
        stream.write(text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", type=Path, required=True)
    parser.add_argument("--worker-config", type=Path, required=True)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--expected-old-image", default=OLD_WORKER)
    parser.add_argument(
        "--canonical-requests-per-minute", type=int, choices=range(4, 121)
    )
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    compose, rollback, worker, old_worker = prepare(
        json.loads(args.service.read_text()),
        json.loads(args.worker_config.read_text()),
        args.worker_image,
        expected_old_image=args.expected_old_image,
        canonical_requests_per_minute=args.canonical_requests_per_minute,
    )
    args.directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, body in [
        ("candidate.yaml", compose),
        ("rollback.yaml", rollback),
        ("worker-candidate.json", json.dumps(worker, indent=2) + "\n"),
        ("worker-rollback.json", json.dumps(old_worker, indent=2) + "\n"),
    ]:
        write_private(args.directory / name, body)


if __name__ == "__main__":
    main()
