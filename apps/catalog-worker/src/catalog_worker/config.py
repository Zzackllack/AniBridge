"""Strict worker configuration; finite limits are part of the protocol pilot."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from catalog_core.identity import PROVIDERS
from catalog_core.json_codec import fields, integer, loads, require

MIB, GIB = 1024**2, 1024**3
LIMITS = {
    "fetch_concurrency": (4, 1, 8),
    "provider_concurrency": (2, 1, 4),
    "provider_request_interval_s": (2, 1, 60),
    "provider_requests_per_hour": (1800, 1, 3600),
    "body_bytes": (8 * MIB, MIB, 16 * MIB),
    "request_deadline_s": (30, 5, 60),
    "title_deadline_s": (120, 30, 300),
    "title_requests_per_slice": (30, 1, 100),
    "ready_queue_size": (32, 1, 128),
    "writer_batch_size": (100, 1, 500),
    "signal_interval_s": (900, 300, 3600),
    "listing_interval_s": (14400, 3600, 86400),
    "active_interval_s": (14400, 3600, 86400),
    "historical_interval_s": (604800, 86400, 2592000),
    "publish_interval_s": (1800, 300, 3600),
    "state_disk_bytes": (20_000_000_000, GIB, 30_000_000_000),
    "public_disk_bytes": (9_000_000_000, 2 * GIB, 30_000_000_000),
    "total_disk_bytes": (30_000_000_000, 4 * GIB, 30_000_000_000),
}


@dataclass(frozen=True)
class Config:
    providers: dict[str, str]
    canonical_sources: dict
    state_dir: Path
    output_dir: Path
    signing_key_file: Path
    source_id: str
    bind_host: str
    bind_port: int
    limits: dict[str, int]
    publication_sources: frozenset[str] = frozenset()
    sitemap_origins: dict[str, list[str]] = field(default_factory=dict)
    provider_settings: dict[str, dict] = field(default_factory=dict)

    def provider_limits(self, provider: str) -> dict[str, int]:
        return {
            **self.limits,
            **self.provider_settings.get(provider, {}).get("limits", {}),
        }

    def headers(self, provider: str) -> dict[str, str]:
        profile = self.provider_settings.get(provider, {}).get("headers", {})
        return {
            "User-Agent": "AniBridge-Metadata/1.0",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "de,en;q=0.8",
            **profile,
        }


def load(path: Path) -> Config:
    raw = fields(
        loads(path.read_bytes(), 65536),
        {
            "providers",
            "canonical_sources",
            "state_dir",
            "output_dir",
            "source_id",
        },
        {
            "bind_host",
            "bind_port",
            "limits",
            "publication_sources",
            "sitemap_origins",
            "signing_key_file",
            "provider_settings",
        },
    )
    providers = raw["providers"]
    require(
        type(providers) is dict
        and 0 < len(providers) <= 3
        and providers.keys() <= PROVIDERS,
        "invalid providers",
    )
    for origin in providers.values():
        require(type(origin) is str, "invalid provider origin")
        url = urlsplit(origin)
        require(
            url.scheme == "https"
            and bool(url.hostname)
            and url.path in {"", "/"}
            and not url.username
            and not url.password
            and not url.query
            and not url.fragment,
            "invalid HTTPS origin",
        )
    sitemap_origins = fields(raw.get("sitemap_origins", {}), set(), {"megakino"})
    for aliases in sitemap_origins.values():
        require(type(aliases) is list and len(aliases) <= 4, "invalid sitemap origins")
        for alias in aliases:
            url = urlsplit(alias)
            require(
                url.scheme == "https"
                and bool(url.hostname)
                and url.path in {"", "/"}
                and not url.username
                and not url.password
                and not url.query
                and not url.fragment,
                "invalid sitemap origin",
            )
    sources = fields(
        raw["canonical_sources"], set(), {"tv", "movie", "tmdb_token_file"}
    )
    require(
        sources.get("tv", "skyhook") in ("skyhook", "off")
        and sources.get("movie", "off") in ("tmdb", "off"),
        "invalid canonical source",
    )
    if sources.get("movie") == "tmdb":
        require(
            type(sources.get("tmdb_token_file")) is str
            and Path(sources["tmdb_token_file"]).is_file(),
            "TMDb credential file required",
        )
    approved = raw.get("publication_sources", [])
    require(
        type(approved) is list and len(approved) <= 16, "invalid publication sources"
    )
    require(
        all(
            type(source) is str and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", source)
            for source in approved
        ),
        "invalid publication source",
    )
    require(len(set(approved)) == len(approved), "duplicate publication source")
    paths = [
        Path(raw.get(key, str(Path(raw["state_dir"]) / "unused-signing-key"))).resolve()
        for key in ("state_dir", "output_dir", "signing_key_file")
    ]
    state, output, key = paths
    require(
        state != output
        and not state.is_relative_to(output)
        and not output.is_relative_to(state),
        "state/output must be separate",
    )
    require(not key.is_relative_to(output), "signing key cannot be served")
    require(
        type(raw["source_id"]) is str
        and re.fullmatch(r"[a-z0-9._-]{1,64}", raw["source_id"]) is not None,
        "invalid source ID",
    )
    supplied = fields(raw.get("limits", {}), set(), set(LIMITS))
    limits = {
        k: integer(supplied.get(k, default), low, high)
        for k, (default, low, high) in LIMITS.items()
    }
    require(
        limits["provider_concurrency"] <= limits["fetch_concurrency"],
        "invalid concurrency",
    )
    require(
        limits["state_disk_bytes"] + limits["public_disk_bytes"]
        <= limits["total_disk_bytes"] - 1_000_000_000,
        "state/output quotas must fit the total disk budget including runtime allowance",
    )
    settings = fields(raw.get("provider_settings", {}), set(), set(providers))
    for provider, values in settings.items():
        fields(values, set(), {"limits", "headers"})
        overrides = fields(
            values.get("limits", {}),
            set(),
            {
                "provider_concurrency",
                "provider_request_interval_s",
                "provider_requests_per_hour",
            },
        )
        for name, value in overrides.items():
            integer(value, LIMITS[name][1], LIMITS[name][2])
        require(
            overrides.get("provider_concurrency", limits["provider_concurrency"])
            <= limits["fetch_concurrency"],
            "invalid provider concurrency",
        )
        profile = fields(
            values.get("headers", {}),
            set(),
            {"User-Agent", "Accept", "Accept-Language", "Referer"},
        )
        for name, value in profile.items():
            require(
                type(value) is str
                and 0 < len(value.encode()) <= 512
                and all(32 <= ord(c) < 127 for c in value),
                "invalid request header",
            )
            if name == "Referer":
                require(
                    value == providers[provider].rstrip("/") + "/",
                    "invalid referer origin",
                )
    host = raw.get("bind_host", "0.0.0.0")
    require(type(host) is str and bool(host), "invalid bind host")
    return Config(
        providers,
        sources,
        state,
        output,
        key,
        raw["source_id"],
        host,
        integer(raw.get("bind_port", 8080), 1, 65535),
        limits,
        frozenset(approved),
        sitemap_origins,
        settings,
    )
