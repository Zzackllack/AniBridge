"""Prepare a Coolify patch/rollback pair from its privately saved service JSON."""

import argparse
import base64
import copy
import json
import re
from pathlib import Path

import yaml


def prepare(service: dict, revision: str) -> tuple[dict, dict]:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("full candidate commit required")
    record = service.get("data", service)
    if record.get("uuid") != "ev7cds2lpqyvqfxpcm4wp4tc":
        raise ValueError("wrong private-pilot service")
    source = record["docker_compose_raw"]
    before = yaml.safe_load(source)
    after = copy.deepcopy(before)
    selected = after["services"]
    if not {"initialize", "collector", "metadata"} <= selected.keys():
        raise ValueError("expected existing private-pilot components")
    for name in ("initialize", "collector", "metadata"):
        image = selected[name]["image"]
        if not image.startswith("anibridge-query-worker:"):
            raise ValueError("unexpected worker image; inspect source before updating")
        selected[name]["image"] = "anibridge-query-worker:" + revision
    if selected["collector"].get("cpus") != 2 or selected["collector"].get(
        "mem_limit"
    ) not in ("512m", "2g"):
        raise ValueError("unexpected collector resource profile")
    # Prove that no storage, network, credential, source, port, log or other
    # service setting changed. Coolify receives its original raw volume names.
    restored = copy.deepcopy(after)
    for name in ("initialize", "collector", "metadata"):
        restored["services"][name]["image"] = before["services"][name]["image"]
    restored["services"]["collector"]["mem_limit"] = before["services"]["collector"][
        "mem_limit"
    ]
    if restored != before:
        raise ValueError("unexpected upgrade mutation")
    return {
        "docker_compose_raw": base64.b64encode(
            yaml.safe_dump(after, sort_keys=False).encode()
        ).decode(),
        "instant_deploy": False,
    }, {
        "docker_compose_raw": base64.b64encode(source.encode()).decode(),
        "instant_deploy": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    candidate, rollback = prepare(json.loads(args.service.read_text()), args.revision)
    args.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name, body in [("candidate.json", candidate), ("rollback.json", rollback)]:
        path = args.directory / name
        path.touch(mode=0o600, exist_ok=False)
        path.write_text(json.dumps(body, indent=2) + "\n")
