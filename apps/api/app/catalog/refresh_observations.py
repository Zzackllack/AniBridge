"""Validate local observations and retain a private release discovery ledger."""

import json
import sqlite3
from contextlib import closing

from catalog_core import identity
from catalog_core.json_codec import dumps, fields, integer, require
from catalog_core.providers.adapters import adapter

from .management_schema import bump
from .storage import writable

TITLE_FIELDS = {
    "title_id",
    "identity_anchor",
    "slug",
    "display_title",
    "search_key",
    "media_type",
    "year",
    "path",
    "observed_at",
    "detail_status",
}
ENTITY_FIELDS = {
    "entity_id",
    "title_id",
    "identity_anchor",
    "kind",
    "native_season",
    "native_episode",
    "display_title",
    "path",
    "observed_at",
}


def cache_kind(kind: str, provider: str) -> str:
    return "refresh_" + kind + ":" + provider


def cached(db: sqlite3.Connection, kind: str, key: str, now: int) -> dict | None:
    row = db.execute(
        "SELECT body FROM catalog_cache WHERE kind=? AND key=? AND expires_at>?",
        (kind, key, now),
    ).fetchone()
    return json.loads(row[0]) if row else None


def put(
    db: sqlite3.Connection,
    kind: str,
    key: str,
    value: dict,
    now: int,
    *,
    ledger: bool = False,
) -> None:
    db.execute(
        "INSERT OR REPLACE INTO catalog_cache VALUES(?,?,?,?,?)",
        (kind, key, dumps(value).decode(), 2**63 - 1 if ledger else now + 86400, now),
    )


def validate(provider: str, title: dict, data: dict, now: int) -> None:
    require(type(data["complete"]) is bool, "refresh completeness")
    integer(data["requests"], 0, 30)
    require(
        type(data["entities"]) is list and len(data["entities"]) <= 30,
        "refresh entity capacity",
    )
    if data["title"] is not None:
        value = fields(data["title"], TITLE_FIELDS)
        require(
            all(
                value[key] == title[key]
                for key in (
                    "title_id",
                    "identity_anchor",
                    "slug",
                    "media_type",
                    "path",
                    "detail_status",
                )
            ),
            "title identity changed",
        )
        require(
            type(value["display_title"]) is str
            and 0 < len(value["display_title"].encode()) <= 512
            and not any(ord(c) < 32 or ord(c) == 127 for c in value["display_title"])
            and value["search_key"] == identity.search_key(value["display_title"]),
            "title label",
        )
        if value["year"] is not None:
            integer(value["year"], 1800, 2200)
        integer(value["observed_at"], 0, now + 300)
    seen = set()
    parser = adapter(provider)
    for value in data["entities"]:
        fields(value, ENTITY_FIELDS | {"languages", "complete"})
        eid = value["entity_id"]
        require(
            eid == identity.entity_id(provider, value["identity_anchor"])
            and eid not in seen
            and value["title_id"] == title["title_id"],
            "entity identity",
        )
        seen.add(eid)
        path = identity.path(value["path"])
        require(path == value["path"] == value["identity_anchor"], "entity path")
        if value["kind"] == "movie":
            require(
                title["media_type"] == "movie"
                and path == title["path"]
                and value["native_season"] is None
                and value["native_episode"] is None,
                "movie identity",
            )
        else:
            # bool compares equal to 0/1 in Python; native coordinates must
            # still be integers from the validated provider path.
            integer(value["native_season"], 0, 2**31 - 1)
            integer(value["native_episode"], 1, 2**31 - 1)
            require(
                value["kind"] == "episode"
                and title["media_type"] == "series"
                and path.startswith(title["path"] + "/")
                and parser.EPISODE.fullmatch(path)
                and tuple(parser.coordinates(path))
                == (value["native_season"], value["native_episode"]),
                "episode identity",
            )
        require(
            type(value["languages"]) is list
            and len(set(value["languages"])) == len(value["languages"])
            and set(value["languages"]) <= identity.LANGUAGES,
            "observed languages",
        )
        require(type(value["complete"]) is bool, "entity completeness")
        integer(value["observed_at"], 0, now + 300)
        require(
            value["display_title"] is None
            or type(value["display_title"]) is str
            and 0 < len(value["display_title"].encode()) <= 512
            and not any(ord(c) < 32 or ord(c) == 127 for c in value["display_title"]),
            "entity label",
        )
    if data["error"] is not None:
        fields(data["error"], {"code", "next_retry_at"})
        require(
            data["error"]["code"]
            in {
                "slice_exhausted",
                "provider_cooldown",
                "rate_limited",
                "challenge_or_block",
                "not_found",
                "transport_failure",
                "unexpected_structure",
                "refresh_failed",
                "clock_error",
            },
            "refresh error",
        )
        if data["error"]["next_retry_at"] is not None:
            integer(data["error"]["next_retry_at"], 0)


def save(store, db, provider: str, title: dict, data: dict, now: int) -> bool:
    validate(provider, title, data, now)
    require(
        writable(
            store.private_db, store.limits["private_metadata_bytes"], len(dumps(data))
        ),
        "storage_full",
    )
    current = store.registry.get(provider)
    require(current is not None, "catalog_unavailable")
    with closing(
        sqlite3.connect(
            (store.directory / current[0]).resolve().as_uri() + "?mode=ro&immutable=1",
            uri=True,
        )
    ) as catalog:
        catalog.row_factory = sqlite3.Row
        observed = catalog.execute(
            "SELECT * FROM title WHERE title_id=?", (title["title_id"],)
        ).fetchone()
        require(
            observed is not None
            and all(
                observed[key] == title[key]
                for key in ("identity_anchor", "media_type", "path")
            ),
            "title identity changed",
        )
        changed = False
        if data["title"] is not None:
            kind = cache_kind("title", provider)
            prior = cached(db, kind, title["title_id"], now)
            baseline = (
                prior
                if prior and prior["observed_at"] > observed["observed_at"]
                else observed
            )
            changed |= any(
                data["title"][key] != baseline[key] for key in ("display_title", "year")
            )
            put(db, kind, title["title_id"], data["title"], now)
        for entity in data["entities"]:
            kind = cache_kind("entity", provider)
            central = catalog.execute(
                "SELECT * FROM entity WHERE entity_id=?", (entity["entity_id"],)
            ).fetchone()
            prior = cached(db, kind, entity["entity_id"], now)
            baseline = (
                prior
                if prior
                and (central is None or prior["observed_at"] > central["observed_at"])
                else central
            )
            central_languages = {
                r[0]
                for r in catalog.execute(
                    "SELECT language FROM release WHERE entity_id=?",
                    (entity["entity_id"],),
                )
            }
            old_languages = (
                set(baseline["languages"])
                if baseline is prior and prior
                else central_languages
            )
            if entity["display_title"] is None and baseline is not None:
                entity = {**entity, "display_title": baseline["display_title"]}
            # A page with unknown labels only contributes positively known
            # offers; it cannot remove any centrally known language variant.
            if not entity["complete"]:
                entity = {
                    **entity,
                    "languages": sorted(set(entity["languages"]) | old_languages),
                }
            changed |= (
                baseline is None
                or any(
                    entity[key] != baseline[key]
                    for key in ENTITY_FIELDS - {"observed_at"}
                )
                or set(entity["languages"]) != old_languages
            )
            releases = []
            for language in entity["languages"]:
                rid = identity.release_id(provider, entity["entity_id"], language)
                kind_seen = cache_kind("seen", provider)
                prior_seen = cached(db, kind_seen, rid, now)
                central_seen = catalog.execute(
                    "SELECT first_seen_at FROM release WHERE release_id=?", (rid,)
                ).fetchone()
                first_seen = min(
                    entity["observed_at"],
                    prior_seen["first_seen_at"]
                    if prior_seen
                    else entity["observed_at"],
                    central_seen[0] if central_seen else entity["observed_at"],
                )
                put(db, kind_seen, rid, {"first_seen_at": first_seen}, now, ledger=True)
                releases.append(
                    {
                        "release_id": rid,
                        "entity_id": entity["entity_id"],
                        "language": language,
                        "first_seen_at": first_seen,
                        "observed_at": entity["observed_at"],
                    }
                )
            put(db, kind, entity["entity_id"], {**entity, "releases": releases}, now)
        if changed:
            bump(db)
        return changed
