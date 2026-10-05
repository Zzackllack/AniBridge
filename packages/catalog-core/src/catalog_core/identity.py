"""Stable identities deliberately exclude labels, quality and source origin."""

import hashlib
import json
import re
import unicodedata
from urllib.parse import quote, unquote, urlsplit

from .json_codec import require

PROVIDERS = frozenset({"aniworld.to", "s.to", "megakino"})
LANGUAGES = frozenset({"de-dub", "en-dub", "de-sub", "en-sub"})
NAMESPACES = frozenset({"tvdb", "tmdb-tv", "tmdb-movie", "imdb"})


def digest(*parts: str) -> str:
    require(all(isinstance(p, str) for p in parts), "identity parts must be strings")
    data = json.dumps(
        [unicodedata.normalize("NFC", p) for p in parts],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(data).hexdigest()


def search_key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join("".join(c if c.isalnum() else " " for c in value).split())


def path(value: str) -> str:
    require(isinstance(value, str) and len(value.encode()) <= 1024, "invalid path")
    require(
        value.startswith("/") and not value.startswith("//"), "relative path required"
    )
    require(not any(ord(c) < 32 or ord(c) == 127 for c in value), "path control")
    require(not any(c in value for c in "\\?#"), "ambiguous path")
    require(not re.search(r"%(?![0-9a-fA-F]{2})", value), "invalid path escape")
    require(
        not re.search(r"%(?:2f|5c|2e|25)", value, re.IGNORECASE),
        "encoded path delimiter",
    )
    parsed = urlsplit(value)
    require(not parsed.netloc and not parsed.scheme, "path origin")
    decoded = unicodedata.normalize("NFC", unquote(value, errors="strict"))
    require(not any(ord(c) < 32 or ord(c) == 127 for c in decoded), "path control")
    require(
        not any(p in {".", "..", ""} for p in decoded[1:].rstrip("/").split("/"))
        or decoded == "/",
        "ambiguous path segments",
    )
    result = quote(decoded.rstrip("/") or "/", safe="/-._~")
    require(len(result.encode()) <= 1024, "path too large")
    return result


def title_id(provider: str, anchor: str) -> str:
    require(type(provider) is str and provider in PROVIDERS, "unknown provider")
    return digest("ab-title-1", provider, path(anchor))


def entity_id(provider: str, anchor: str) -> str:
    require(type(provider) is str and provider in PROVIDERS, "unknown provider")
    return digest("ab-entity-1", provider, path(anchor))


def release_id(provider: str, entity: str, language: str) -> str:
    require(
        type(provider) is str
        and provider in PROVIDERS
        and type(language) is str
        and language in LANGUAGES,
        "unknown release variant",
    )
    return digest("ab-release-1", provider, entity, language)


def mapping_id(provider: str, title: str, namespace: str, external_id: str) -> str:
    validate_external_id(namespace, external_id)
    return digest("ab-map-1", provider, title, namespace, external_id)


def infohash(release: str, mode: str) -> str:
    require(type(mode) is str and mode in {"download", "strm"}, "unknown mode")
    return digest("ab-grab-1", release, mode)[:40]


def validate_external_id(namespace: str, value: str) -> None:
    require(
        type(namespace) is str and namespace in NAMESPACES and isinstance(value, str),
        "unknown ID namespace",
    )
    pattern = r"tt[0-9]{7,12}" if namespace == "imdb" else r"[1-9][0-9]*"
    require(
        len(value) <= 128 and re.fullmatch(pattern, value) is not None,
        "invalid external ID",
    )
