"""Strict local manifest for Filmo's declared media renditions."""

import re
from pathlib import Path

from catalog_core.json_codec import loads

MAX_TRACK_MANIFEST_BYTES = 8192
MAX_MEDIA_INPUTS = 16
_LANGUAGE = re.compile(r"^[a-z]{3}$")


def validate_tracks_manifest(
    manifest_path: Path, root: Path, inputs: list[Path]
) -> tuple[dict, ...]:
    """Bind a small sidecar to the exact safe files emitted by transfer."""
    if not isinstance(manifest_path, Path) or not isinstance(root, Path):
        raise ValueError("invalid track paths")
    root = root.resolve(strict=True)
    if manifest_path.is_symlink() or not _contained(manifest_path, root):
        raise ValueError("invalid track manifest path")
    if (
        not manifest_path.is_file()
        or manifest_path.stat().st_size > MAX_TRACK_MANIFEST_BYTES
    ):
        raise ValueError("invalid track manifest")
    raw = loads(manifest_path.read_bytes(), MAX_TRACK_MANIFEST_BYTES)
    if (
        type(raw) is not dict
        or set(raw) != {"version", "tracks"}
        or type(raw["version"]) is not int
        or raw["version"] != 1
    ):
        raise ValueError("invalid track manifest")
    records = raw["tracks"]
    if type(records) is not list or not 1 <= len(records) <= MAX_MEDIA_INPUTS:
        raise ValueError("invalid track manifest")
    if (
        type(inputs) is not list
        or len(inputs) != len(records)
        or not all(
            isinstance(path, Path) and _safe_input(path, root) for path in inputs
        )
    ):
        raise ValueError("invalid track inputs")

    checked = []
    seen = set()
    kind_counts = {"video": 0, "audio": 0, "subtitle": 0}
    for record, path in zip(records, inputs, strict=True):
        if type(record) is not dict or set(record) != {
            "file",
            "kind",
            "language",
            "format",
        }:
            raise ValueError("invalid track record")
        name, kind, language, format = (
            record["file"],
            record["kind"],
            record["language"],
            record["format"],
        )
        if (
            type(name) is not str
            or not name
            or Path(name).name != name
            or name in {".", ".."}
            or path.name != name
            or name in seen
            or type(kind) is not str
            or kind not in kind_counts
        ):
            raise ValueError("invalid track identity")
        if kind == "video":
            if language is not None or format is not None:
                raise ValueError("invalid video metadata")
        elif kind == "audio":
            if (
                type(language) is not str
                or not _LANGUAGE.fullmatch(language)
                or format is not None
            ):
                raise ValueError("invalid audio metadata")
        elif kind == "subtitle":
            if (
                type(language) is not str
                or not _LANGUAGE.fullmatch(language)
                or format not in ("srt", "vtt")
            ):
                raise ValueError("invalid subtitle metadata")
        seen.add(name)
        kind_counts[kind] += 1
        checked.append(record)
    if kind_counts["video"] != 1 or records[0]["kind"] != "video":
        raise ValueError("invalid video track count")
    if kind_counts["audio"] > 8 or kind_counts["subtitle"] > 8:
        raise ValueError("too many tracks")
    return tuple(checked)


def _contained(path: Path, root: Path) -> bool:
    try:
        absolute = path.absolute()
        relative = absolute.relative_to(root)
    except ValueError:
        return False
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return False
    try:
        return absolute.resolve(strict=True).is_relative_to(root)
    except OSError, RuntimeError:
        return False


def _safe_input(path: Path, root: Path) -> bool:
    return path.is_file() and not path.is_symlink() and _contained(path, root)
