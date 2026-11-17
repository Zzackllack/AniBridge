"""Explicit collector selection from environment with a legacy default."""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from catalog_core.json_codec import require


@dataclass(frozen=True)
class Config:
    mode: str = "legacy"
    origin: str = ""
    source_id: str = ""
    token_file: Path | None = None
    allow_private_http: bool = False
    api_token: str = field(default="", repr=False)

    def bearer_token(self) -> str:
        """Read mounted credentials when consumed; never include them in errors."""
        token = self.api_token
        if self.token_file is not None:
            try:
                with self.token_file.open(encoding="utf-8") as handle:
                    token = handle.read(1025)
                require(len(token) <= 1024, "invalid bearer token file")
                token = token.strip()
            except OSError, UnicodeError, ValueError:
                raise ValueError("invalid bearer token file") from None
        require(
            16 <= len(token) <= 512 and all(33 <= ord(c) <= 126 for c in token),
            "invalid catalog bearer token",
        )
        return token


def _query(
    origin: str,
    source_id: str,
    token_file: str | None,
    allow_private_http: bool,
    api_token: str = "",
) -> Config:
    require(
        isinstance(source_id, str) and re.fullmatch(r"[a-z0-9._-]{1,64}", source_id),
        "invalid source ID",
    )
    require(type(allow_private_http) is bool, "invalid HTTP opt-in")
    require(isinstance(origin, str) and bool(origin), "query source required")
    require(
        not any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in origin),
        "invalid origin",
    )
    try:
        url = urlsplit(origin)
        # Accessing port validates malformed numeric/range values too.
        port = url.port
    except ValueError:
        raise ValueError("invalid origin") from None
    require(
        url.scheme == "https"
        or url.scheme == "http"
        and (url.hostname in {"127.0.0.1", "localhost"} or allow_private_http),
        "HTTPS required",
    )
    require(
        bool(url.hostname)
        and url.username is None
        and url.password is None
        and not url.query
        and not url.fragment
        and url.path in {"", "/"}
        and port != 0,
        "invalid origin",
    )
    require(
        token_file is None or isinstance(token_file, str) and bool(token_file),
        "invalid bearer token file",
    )
    config = Config(
        "query",
        origin,
        source_id,
        Path(token_file) if token_file is not None else None,
        allow_private_http,
        api_token,
    )
    config.bearer_token()
    return config


def from_env(environ: Mapping[str, str] | None = None) -> Config:
    """Select one complete source from environment values only."""
    env = os.environ if environ is None else environ
    names = (
        "CATALOG_MODE",
        "CATALOG_API_URL",
        "CATALOG_SOURCE_ID",
        "CATALOG_API_TOKEN",
        "CATALOG_API_TOKEN_FILE",
        "CATALOG_ALLOW_PRIVATE_HTTP",
    )
    configured = {name for name in names if env.get(name, "").strip()}
    require(
        not env.get("CATALOG_CONFIG_FILE", "").strip(),
        "CATALOG_CONFIG_FILE is no longer supported; use CATALOG_MODE and "
        "the catalog environment settings",
    )
    mode = env.get("CATALOG_MODE", "").strip() or "legacy"
    require(mode in {"legacy", "query"}, "CATALOG_MODE must be legacy or query")
    if mode == "legacy":
        require(
            not configured - {"CATALOG_MODE"},
            "collector settings require CATALOG_MODE=query",
        )
        return Config()
    private_http = env.get("CATALOG_ALLOW_PRIVATE_HTTP", "").strip().lower()
    require(
        private_http in {"", "true", "false", "1", "0", "yes", "no", "on", "off"},
        "CATALOG_ALLOW_PRIVATE_HTTP must be a boolean",
    )
    token = env.get("CATALOG_API_TOKEN", "")
    token_file = env.get("CATALOG_API_TOKEN_FILE", "").strip()
    require(
        bool(token) != bool(token_file),
        "set exactly one of CATALOG_API_TOKEN and CATALOG_API_TOKEN_FILE",
    )
    return _query(
        env.get("CATALOG_API_URL", "").strip(),
        env.get("CATALOG_SOURCE_ID", "").strip(),
        token_file or None,
        private_http in {"true", "1", "yes", "on"},
        token,
    )
