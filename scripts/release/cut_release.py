#!/usr/bin/env python3
"""
Compute and apply AniBridge release version bumps.

This script is intentionally repo-owned and deterministic so CI, not local
developer state, becomes the release authority.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = ROOT / "VERSION"
PYPROJECT_FILE = ROOT / "pyproject.toml"
OPENAPI_FILE = ROOT / "docs/src/openapi.json"
DOCS_PACKAGE_FILE = ROOT / "docs/package.json"

SEMVER_RE = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$")


@dataclass(frozen=True)
class ReleasePlan:
    previous_version: str
    next_version: str
    release_type: str
    release_tag: str
    previous_tag: str | None
    files: tuple[str, ...]


def parse_version(value: str) -> tuple[int, int, int]:
    match = SEMVER_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Unsupported version string: {value!r}")
    return tuple(int(match.group(name)) for name in ("major", "minor", "patch"))


def format_version(parts: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in parts)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def bump_version(current: str, release_type: str) -> str:
    major, minor, patch = parse_version(current)
    if release_type == "patch":
        return format_version((major, minor, patch + 1))
    if release_type == "minor":
        return format_version((major, minor + 1, 0))
    if release_type == "major":
        return format_version((major + 1, 0, 0))
    raise ValueError(f"Unsupported release type: {release_type}")


def run_git(
    *args: str,
    check: bool = True,
    timeout: float | None = 30,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def git_output(*args: str, timeout: float | None = 30) -> str:
    return run_git(*args, timeout=timeout).stdout.strip()


def ensure_clean_worktree() -> None:
    status = git_output("status", "--short")
    if status:
        raise RuntimeError("Refusing to cut release from a dirty worktree.")


def latest_release_tag(exclude: Iterable[str] = ()) -> str | None:
    excluded = set(exclude)
    tags = [
        tag
        for tag in git_output("tag", "--sort=-creatordate").splitlines()
        if tag.startswith("v") and tag not in excluded
    ]
    return tags[0] if tags else None


def build_release_plan(release_type: str) -> ReleasePlan:
    current_version = VERSION_FILE.read_text(encoding="utf-8").strip()
    next_version = bump_version(current_version, release_type)
    return ReleasePlan(
        previous_version=current_version,
        next_version=next_version,
        release_type=release_type,
        release_tag=f"v{next_version}",
        previous_tag=latest_release_tag(),
        files=(
            display_path(VERSION_FILE),
            display_path(PYPROJECT_FILE),
            display_path(OPENAPI_FILE),
            display_path(DOCS_PACKAGE_FILE),
        ),
    )


def replace_once(path: Path, pattern: str, replacement: str) -> None:
    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"Could not update version in {display_path(path)}")
    path.write_text(updated, encoding="utf-8")


def apply_release_plan(plan: ReleasePlan) -> None:
    VERSION_FILE.write_text(plan.next_version + "\n", encoding="utf-8")
    replace_once(
        PYPROJECT_FILE,
        r'^(version = ")\d+\.\d+\.\d+(")$',
        rf"\g<1>{plan.next_version}\2",
    )
    replace_once(
        OPENAPI_FILE,
        r'^(\s*"version": ")\d+\.\d+\.\d+(")(,?)$',
        rf"\g<1>{plan.next_version}\2\3",
    )
    replace_once(
        DOCS_PACKAGE_FILE,
        r'^(\s*"version": ")\d+\.\d+\.\d+(")(,?)$',
        rf"\g<1>{plan.next_version}\2\3",
    )


def create_commit(plan: ReleasePlan) -> dict[str, str]:
    run_git("add", *plan.files)
    commit_message = f"chore(release): cut {plan.release_tag}"
    run_git("commit", "-m", commit_message)
    return {
        "commit_message": commit_message,
        "commit_sha": git_output("rev-parse", "HEAD"),
    }


def create_tag(plan: ReleasePlan) -> dict[str, str]:
    tag_message = f"Release {plan.release_tag}"
    run_git("tag", "-a", plan.release_tag, "-m", tag_message)
    return {"tag_message": tag_message}


def plan_to_dict(plan: ReleasePlan) -> dict[str, object]:
    return {
        "previous_version": plan.previous_version,
        "next_version": plan.next_version,
        "release_type": plan.release_type,
        "release_tag": plan.release_tag,
        "previous_tag": plan.previous_tag,
        "files": list(plan.files),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release-type",
        choices=("patch", "minor", "major"),
        required=True,
        help="Semantic version increment to apply.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the version changes to disk.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Create the release commit after applying changes.",
    )
    parser.add_argument(
        "--tag",
        action="store_true",
        help="Create the annotated release tag after committing.",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Skip the clean worktree check.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional path to write release metadata as JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.commit and not args.apply:
        raise SystemExit("--commit requires --apply")
    if args.tag and not args.commit:
        raise SystemExit("--tag requires --commit")

    plan = build_release_plan(args.release_type)
    result = plan_to_dict(plan)

    if args.apply:
        if not args.allow_dirty:
            ensure_clean_worktree()
        if git_output("tag", "-l", plan.release_tag):
            raise SystemExit(f"Tag already exists: {plan.release_tag}")
        apply_release_plan(plan)

    if args.commit:
        result.update(create_commit(plan))
    if args.tag:
        result.update(create_tag(plan))

    payload = json.dumps(result, indent=2) + "\n"
    if args.output_json:
        Path(args.output_json).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
