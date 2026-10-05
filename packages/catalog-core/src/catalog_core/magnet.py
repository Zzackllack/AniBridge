"""Self-contained v2 grabs: integrity is checked independently of availability."""

import base64
import re
from urllib.parse import parse_qs, urlencode, urlsplit

from . import identity as ident
from .json_codec import ContractError, dumps, fields, integer, loads, require

PAYLOAD_FIELDS = {
    "provider",
    "title_id",
    "entity_id",
    "release_id",
    "title_anchor",
    "entity_anchor",
    "slug",
    "path",
    "kind",
    "native_season",
    "native_episode",
    "language",
    "mode",
    "canonical",
}


def validate(payload: dict) -> dict:
    p = fields(payload, PAYLOAD_FIELDS)
    require(
        p["title_id"] == ident.title_id(p["provider"], p["title_anchor"]),
        "invalid title ID",
    )
    require(
        p["entity_id"] == ident.entity_id(p["provider"], p["entity_anchor"]),
        "invalid entity ID",
    )
    require(
        p["release_id"]
        == ident.release_id(p["provider"], p["entity_id"], p["language"]),
        "invalid release ID",
    )
    require(
        type(p["mode"]) is str and p["mode"] in {"download", "strm"},
        "invalid grab mode",
    )
    for key in ("title_anchor", "entity_anchor", "path"):
        require(ident.path(p[key]) == p[key], "noncanonical grab path")
    require(
        type(p["slug"]) is str and 0 < len(p["slug"].encode()) <= 256, "invalid slug"
    )
    require(
        not any(c in p["slug"] for c in "/\\?#%")
        and p["slug"] not in {".", ".."}
        and not any(ord(c) < 32 for c in p["slug"]),
        "invalid slug",
    )
    require(
        type(p["kind"]) is str and p["kind"] in {"episode", "movie"}, "invalid kind"
    )
    if p["kind"] == "movie":
        require(
            p["native_season"] is None and p["native_episode"] is None,
            "movie coordinates",
        )
    else:
        integer(p["native_season"])
        integer(p["native_episode"], 1)
    canonical = p["canonical"]
    if canonical is not None:
        fields(canonical, {"namespace", "external_id", "season", "episode"})
        ident.validate_external_id(canonical["namespace"], canonical["external_id"])
        if p["kind"] == "movie":
            require(
                canonical["namespace"] in {"tmdb-movie", "imdb"}
                and canonical["season"] is None
                and canonical["episode"] is None,
                "invalid movie mapping",
            )
        else:
            require(
                canonical["namespace"] in {"tvdb", "tmdb-tv"},
                "invalid episode namespace",
            )
            integer(canonical["season"])
            integer(canonical["episode"], 1)
    return p


def encode(payload: dict, label: str) -> str:
    p = validate(payload)
    raw = dumps(p)
    require(len(raw) <= 8192, "grab too large")
    return "magnet:?" + urlencode(
        {
            "xt": "urn:btih:" + ident.infohash(p["release_id"], p["mode"]),
            "dn": label,
            "ab_v": "2",
            "ab_data": base64.urlsafe_b64encode(raw).decode().rstrip("="),
        },
        # Sonarr's MonoTorrent parser reads the xt URN without URL-decoding it.
        # Keep its separators literal; payload/base64 and display escaping stay
        # canonical and no identity input changes.
        safe=":",
    )


def decode(value: str) -> tuple[str, dict, str]:
    require(len(value.encode()) <= 16384, "magnet too large")
    url = urlsplit(value)
    require(
        url.scheme == "magnet" and not url.netloc and not url.path and not url.fragment,
        "invalid magnet",
    )
    try:
        params = parse_qs(
            url.query,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=4,
            errors="strict",
        )
    except ValueError as exc:
        raise ContractError("invalid magnet fields") from exc
    require(
        set(params) == {"xt", "dn", "ab_v", "ab_data"}
        and all(len(v) == 1 for v in params.values()),
        "invalid magnet fields",
    )
    require(params["ab_v"] == ["2"], "unsupported magnet version")
    token = params["ab_data"][0]
    require(
        re.fullmatch(r"[A-Za-z0-9_-]+", token) is not None, "invalid payload encoding"
    )
    raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    require(
        base64.urlsafe_b64encode(raw).decode().rstrip("=") == token,
        "noncanonical payload encoding",
    )
    payload = validate(loads(raw, 8192))
    infohash = ident.infohash(payload["release_id"], payload["mode"])
    require(params["xt"] == ["urn:btih:" + infohash], "grab hash mismatch")
    return infohash, payload, params["dn"][0]
