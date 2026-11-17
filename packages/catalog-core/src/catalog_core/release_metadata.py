"""Bounded declared source evidence, distinct from measured media properties.

The native offer anchor identifies a selection. Quality labels and rotating
player tokens must never become its identity or a substitute for that selection.
"""

import re
import unicodedata

from .json_codec import dumps, fields, loads, require

FIELDS = {
    "variant_anchor",
    "native_id",
    "host",
    "language_label",
    "audio_languages",
    "subtitle_languages",
    "audio_role",
    "subtitle_mode",
    "quality",
}
SOURCES = frozenset(
    {
        "unknown",
        "bluray",
        "web",
        "webdl",
        "webrip",
        "cam",
        "telesync",
        "telecine",
        "dvd",
        "tv",
    }
)


def text(value: object, maximum: int) -> bool:
    return (
        type(value) is str
        and 0 < len(value.encode()) <= maximum
        and not any(ord(c) < 32 or ord(c) == 127 for c in value)
    )


def valid_language(value: object) -> bool:
    """Accept normalized ISO-639-3 shaped tags, optionally with subtags."""
    return (
        type(value) is str
        and re.fullmatch(r"[a-z]{3}(?:-[a-z0-9]{2,8}){0,3}", value) is not None
    )


def validate(value: dict) -> dict:
    metadata = fields(value, FIELDS)
    require(text(metadata["variant_anchor"], 256), "invalid variant anchor")
    require(
        re.fullmatch(r"[A-Za-z0-9._:-]+", metadata["variant_anchor"]) is not None,
        "invalid variant anchor",
    )
    require(
        type(metadata["native_id"]) is str
        and re.fullmatch(r"[1-9][0-9]{0,63}", metadata["native_id"]) is not None,
        "invalid native offer ID",
    )
    require(
        metadata["variant_anchor"].startswith(metadata["native_id"] + ":"),
        "native offer anchor mismatch",
    )
    require(
        text(metadata["host"], 64)
        and re.fullmatch(r"[A-Za-z0-9 ._-]+", metadata["host"]) is not None,
        "invalid offer host",
    )
    require(text(metadata["language_label"], 128), "invalid declared language")
    for name in ("audio_languages", "subtitle_languages"):
        languages = metadata[name]
        if name == "subtitle_languages" and languages is None:
            continue
        require(
            type(languages) is list and len(languages) <= 16, "invalid track languages"
        )
        require(
            all(valid_language(item) for item in languages)
            and len(set(languages)) == len(languages),
            "invalid track languages",
        )
        require(
            name != "audio_languages" or bool(languages), "missing audio language state"
        )
    require(
        metadata["audio_role"] in ("original", "dubbed", "unknown"),
        "invalid audio role",
    )
    require(
        metadata["subtitle_mode"] in ("soft", "hard", "none", "unknown"),
        "invalid subtitle mode",
    )
    require(
        metadata["subtitle_mode"] != "none" or metadata["subtitle_languages"] == [],
        "contradictory subtitles",
    )
    quality = fields(metadata["quality"], {"labels", "source", "resolution"})
    require(
        type(quality["source"]) is str and quality["source"] in SOURCES,
        "invalid quality source",
    )
    require(
        type(quality["labels"]) is list
        and len(quality["labels"]) <= 16
        and all(text(label, 64) for label in quality["labels"]),
        "invalid quality labels",
    )
    require(
        quality["resolution"] is None
        or type(quality["resolution"]) is int
        and 1 <= quality["resolution"] <= 16384,
        "invalid declared resolution",
    )
    require(len(dumps(metadata)) <= 4096, "release metadata overflow")
    return metadata


def language(metadata: dict) -> str:
    values = validate(metadata)["audio_languages"]
    return values[0] if len(values) == 1 else "mul"


def decode(value: str) -> dict:
    require(type(value) is str, "invalid release metadata storage")
    return validate(loads(value.encode(), 4096))


def same_selection(first: dict, second: dict) -> bool:
    """Ignore cosmetic spelling changes, never substantive declared evidence."""

    def normalized(value: dict) -> dict:
        checked = validate(value)

        def label(text: str) -> str:
            return " ".join(unicodedata.normalize("NFKC", text).casefold().split())

        return {
            **checked,
            "host": label(checked["host"]),
            "language_label": label(checked["language_label"]),
            "audio_languages": sorted(checked["audio_languages"]),
            "subtitle_languages": None
            if checked["subtitle_languages"] is None
            else sorted(checked["subtitle_languages"]),
            "quality": {
                **checked["quality"],
                "labels": sorted(
                    {label(item) for item in checked["quality"]["labels"]}
                ),
            },
        }

    return normalized(first) == normalized(second)
