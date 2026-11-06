"""Strict, explicit query pilot selection; missing configuration preserves mainline."""

from dataclasses import dataclass
from pathlib import Path

from catalog_core.json_codec import fields, loads, require


@dataclass(frozen=True)
class Config:
    mode: str = "legacy"
    origin: str = ""
    source_id: str = ""
    token_file: Path | None = None
    allow_private_http: bool = False


def load(filename: str | None) -> Config:
    if not filename:
        return Config()
    raw = fields(
        loads(Path(filename).read_bytes(), 65536),
        {"mode"},
        {"origin", "source_id", "token_file", "allow_private_http"},
    )
    require(raw["mode"] in {"legacy", "query"}, "invalid catalog mode")
    if raw["mode"] == "legacy":
        require(set(raw) == {"mode"}, "legacy takes no source configuration")
        return Config()
    require(
        {"origin", "source_id", "token_file"} <= raw.keys(), "query source required"
    )
    import re

    require(
        isinstance(raw["source_id"], str)
        and re.fullmatch(r"[a-z0-9._-]{1,64}", raw["source_id"]),
        "invalid source ID",
    )
    require(type(raw.get("allow_private_http", False)) is bool, "invalid HTTP opt-in")
    token_file = Path(raw["token_file"])
    require(
        token_file.is_file() and 16 <= len(token_file.read_text().strip()) <= 512,
        "invalid bearer token file",
    )
    # URL validation has no transport side effects and runs again in Client.
    from urllib.parse import urlsplit

    url = urlsplit(raw["origin"])
    require(
        url.scheme == "https"
        or url.scheme == "http"
        and (
            url.hostname in {"127.0.0.1", "localhost"}
            or raw.get("allow_private_http", False)
        ),
        "HTTPS required",
    )
    require(
        bool(url.hostname)
        and not url.username
        and not url.password
        and not url.query
        and not url.fragment
        and url.path in {"", "/"},
        "invalid origin",
    )
    return Config(
        "query",
        raw["origin"],
        raw["source_id"],
        token_file,
        raw.get("allow_private_http", False),
    )
