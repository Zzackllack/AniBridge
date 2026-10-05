"""Complete bounded native batches, corrected before canonical policy/pagination."""

import asyncio
import json
import sqlite3
import tempfile
from contextlib import closing, contextmanager
from dataclasses import replace
from pathlib import Path

from catalog_core import identity, query, schema
from catalog_core.json_codec import dumps, require
from catalog_core.protocol import Request, Response
from catalog_core.query_client import Client, Result, Unavailable

from .async_database import call
from .override_view import view


class LocalRead:
    def __init__(self, database: Path, metadata: dict, overrides: list[dict]) -> None:
        self.database, self.metadata, self.overrides = database, metadata, overrides
        self.providers = (metadata["provider"],)

    @contextmanager
    def acquire(self):
        db = schema.connect(self.database)
        private = sqlite3.connect(":memory:")
        private.row_factory = sqlite3.Row
        private.execute(
            "CREATE TABLE catalog_override(id TEXT,provider TEXT,title_id TEXT,entity_id TEXT,namespace TEXT,body TEXT,version INTEGER,created_at INTEGER,updated_at INTEGER)"
        )
        private.execute(
            "CREATE TABLE catalog_cache(kind TEXT,key TEXT,body TEXT,expires_at INTEGER,used_at INTEGER)"
        )
        private.executemany(
            "INSERT INTO catalog_override VALUES(?,?,?,?,?,?,?,?,?)",
            [
                tuple(
                    row[name]
                    for name in (
                        "id",
                        "provider",
                        "title_id",
                        "entity_id",
                        "namespace",
                        "body",
                        "version",
                        "created_at",
                        "updated_at",
                    )
                )
                for row in self.overrides
            ],
        )
        try:
            yield {self.providers[0]: (db, self.metadata)}, private
        finally:
            db.close()
            private.close()


def materialize(filename: Path, responses: list[Response]) -> dict:
    """Small request-owned schema1 view; never a full provider download."""
    db = schema.create(filename)
    metadata = responses[0]
    provider = metadata.provider
    seen_titles, seen_entities, seen_maps, seen_episodes, seen_releases = (
        set(),
        set(),
        set(),
        set(),
        set(),
    )
    try:
        with db:
            db.execute(
                "INSERT INTO catalog VALUES(1,?,1,1,?)",
                (provider, metadata.listing_checked_at),
            )
            for response in responses:
                for title in response.titles:
                    if title.title_id not in seen_titles:
                        db.execute(
                            "INSERT INTO title VALUES(?,?,?,?,?,?,?,?,?,?)",
                            tuple(
                                title.model_dump()[key]
                                for key in (
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
                                )
                            ),
                        )
                        for alias in title.aliases:
                            db.execute(
                                "INSERT OR IGNORE INTO alias VALUES(?,?,?)",
                                (title.title_id, identity.search_key(alias), alias),
                            )
                        seen_titles.add(title.title_id)
                    for mapping in title.mappings:
                        if mapping.mapping_id not in seen_maps:
                            db.execute(
                                "INSERT INTO canonical_title VALUES(?,?,?,?,?,?,?)",
                                tuple(mapping.model_dump().values()),
                            )
                            seen_maps.add(mapping.mapping_id)
                for row in response.rows:
                    if row.entity_id not in seen_entities:
                        db.execute(
                            "INSERT INTO entity VALUES(?,?,?,?,?,?,?,?,?)",
                            (
                                row.entity_id,
                                row.title_id,
                                row.entity_anchor,
                                row.kind,
                                row.native_season,
                                row.native_episode,
                                None,
                                row.path,
                                row.observed_at,
                            ),
                        )
                        seen_entities.add(row.entity_id)
                    if row.release_id not in seen_releases:
                        db.execute(
                            "INSERT INTO release VALUES(?,?,?,?,?)",
                            (
                                row.release_id,
                                row.entity_id,
                                row.language,
                                row.first_seen_at,
                                row.observed_at,
                            ),
                        )
                        seen_releases.add(row.release_id)
                    for mapping in row.mappings:
                        key = (mapping.mapping_id, mapping.entity_id)
                        if key not in seen_episodes:
                            db.execute(
                                "INSERT INTO canonical_episode VALUES(?,?,?,?,?,?,?)",
                                tuple(mapping.model_dump().values()),
                            )
                            seen_episodes.add(key)
    finally:
        db.close()
    return {
        "provider": provider,
        "catalog_schema_version": 1,
        "artifact": {"sqlite_sha256": metadata.snapshot_digest},
        "counts": {"release": len(seen_releases)},
    }


def overrides(database: Path, provider: str = "aniworld.to") -> list[dict]:
    with closing(
        sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.2)
    ) as db:
        db.row_factory = sqlite3.Row
        rows = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM catalog_override WHERE provider=? AND json_extract(body,'$.enabled')=1 LIMIT 1001",
                (provider,),
            )
        ]
        require(len(rows) <= 1000, "query_too_broad")
        return rows


class Search:
    def __init__(
        self,
        client: Client,
        database: Path,
        directory: Path,
        provider: str = "aniworld.to",
    ) -> None:
        self.client, self.database, self.directory = client, database, directory
        self.active = 0
        self.provider = provider

    async def candidates(
        self,
        params: dict[str, str],
        parsed: query.Query,
        local: list[dict],
        results: list[Result],
    ) -> set[str]:
        remote = {
            key: value
            for key, value in params.items()
            if key in {"t", "q", "tvdbid", "tmdbid", "imdbid"}
        }
        response = await self.fetch(Request(operation="titles", params=remote), results)
        selected = {title.title_id for title in response.titles}
        bodies = [json.loads(row["body"]) for row in local]
        # Corrections can introduce an ID that the service has never associated.
        for body in bodies:
            if (
                parsed.ids.get(body["target"]["namespace"])
                == body["target"]["external_id"]
            ):
                selected.add(body["title_id"])
        targets = {
            (body["target"]["namespace"], body["target"]["external_id"])
            for body in bodies
            if body["title_id"] in selected
        }
        require(len(targets) <= 8, "query_too_broad")
        # Look up target IDs normally to detect published assignment conflicts.
        # No reason, fingerprint, corrected coordinates or override body is sent.
        for namespace, value in sorted(targets):
            key = {
                "tvdb": "tvdbid",
                "tmdb-tv": "tmdbid",
                "tmdb-movie": "tmdbid",
                "imdb": "imdbid",
            }[namespace]
            response = await self.fetch(
                Request(
                    operation="titles",
                    params={
                        "t": "movie" if namespace == "tmdb-movie" else parsed.mode,
                        key: value,
                    },
                ),
                results,
            )
            selected.update(title.title_id for title in response.titles)
        require(len(selected) <= 200, "query_too_broad")
        return selected

    async def fetch(self, request: Request, results: list[Result]) -> Response:
        request = request.model_copy(update={"provider": self.provider})
        require(len(dumps(request.model_dump())) <= 16384, "query_too_broad")
        result = await self.client.fetch(request)
        results.append(result)
        return result.response

    async def batches(
        self,
        params: dict[str, str],
        parsed: query.Query,
        local: list[dict],
        modes: tuple[str, ...],
        languages: dict[str, set[str]] | None,
        results: list[Result],
    ) -> list[Response]:
        if parsed.recent:
            # Corrections cannot change kind/language/date. Filter these remotely,
            # then apply coordinate corrections to the bounded page locally.
            remote = {
                key: value
                for key, value in params.items()
                if key in {"t", "maxage", "year", "cat"}
            }
            remote.setdefault("t", parsed.mode)
            request = Request(
                operation="recent",
                params=remote,
                limit=min(100, (parsed.limit + len(modes) - 1) // len(modes) + 1),
                offset=parsed.offset // len(modes),
                languages=sorted(
                    (languages or {}).get(self.provider, identity.LANGUAGES)
                ),
            )
            pages = []
            end = (parsed.offset + parsed.limit + len(modes) - 1) // len(modes)
            for offset in range(request.offset, end, 100):
                batch = await self.fetch(
                    request.model_copy(
                        update={"offset": offset, "limit": min(100, end - offset)}
                    ),
                    results,
                )
                pages.append(batch)
                if offset + len(batch.rows) >= batch.total:
                    break
            return pages
        selected = await self.candidates(params, parsed, local, results)
        if not selected:
            return [results[0].response]
        batches = []
        for offset in range(0, 2000, 500):
            batch = await self.fetch(
                Request(
                    operation="native",
                    params={"t": "search"},
                    title_ids=sorted(selected),
                    offset=offset,
                    coordinate_namespace="tmdb-tv"
                    if "tmdb-tv" in parsed.ids and "tvdb" not in parsed.ids
                    else "tvdb",
                    season=parsed.season,
                    episode=parsed.episode,
                    include_entities=sorted(
                        {
                            row["entity_id"]
                            for row in local
                            if row["title_id"] in selected and row["entity_id"]
                        }
                    ),
                    languages=sorted(
                        (languages or {}).get(self.provider, identity.LANGUAGES)
                    ),
                ),
                results,
            )
            require(batch.total <= 2000, "query_too_broad")
            batches.append(batch)
            if offset + len(batch.rows) >= batch.total:
                break
        return batches

    async def project(
        self,
        batches: list[Response],
        parsed: query.Query,
        local: list[dict],
        *,
        now: int,
        modes: tuple[str, ...],
        languages: dict[str, set[str]] | None,
        anime_category: int,
        movie_category: int,
    ) -> tuple[list[dict], int, dict[str, str]]:
        with tempfile.TemporaryDirectory(
            prefix="query-", dir=self.directory
        ) as temporary:
            filename = Path(temporary) / "rows.sqlite"
            metadata = await call(materialize, filename, batches)
            local_query = (
                replace(parsed, offset=0, limit=10000) if parsed.recent else parsed
            )
            rows, total, headers = await call(
                query.query,
                LocalRead(filename, metadata, local),
                local_query,
                now=now,
                modes=modes,
                languages=languages,
                anime_category=anime_category,
                movie_category=movie_category,
                mapping_view=view,
            )
        if parsed.recent:
            total = batches[0].total * len(modes)
            if parsed.categories is not None and not parsed.categories.intersection(
                {
                    anime_category if self.provider == "aniworld.to" else 5000,
                    movie_category,
                }
            ):
                rows, total = [], 0
            start = parsed.offset % len(modes)
            rows = rows[start : start + parsed.limit]
        return rows, total, headers

    async def search(
        self,
        params: dict[str, str],
        *,
        now: int,
        modes: tuple[str, ...] = ("download",),
        languages: dict[str, set[str]] | None = None,
        anime_category: int = 5070,
        movie_category: int = 2000,
        _window: int | None = None,
    ) -> tuple[list[dict], int, dict[str, str]]:
        if self.active >= 8:
            raise Unavailable("search_busy")
        self.active += 1
        try:
            async with asyncio.timeout(15):
                parsed = query.parse(params)
                if _window is not None:
                    parsed = replace(parsed, offset=0, limit=_window)
                local = await call(overrides, self.database, self.provider)
                for attempt in range(2):
                    results: list[Result] = []
                    batches = await self.batches(
                        params, parsed, local, modes, languages, results
                    )
                    if (
                        len(
                            {
                                (r.response.revision, r.response.snapshot_digest)
                                for r in results
                            }
                        )
                        != 1
                    ):
                        self.client.cache.clear()
                        if attempt == 0:
                            continue
                        raise Unavailable("catalog_changed")
                    rows, total, headers = await self.project(
                        batches,
                        parsed,
                        local,
                        now=now,
                        modes=modes,
                        languages=languages,
                        anime_category=anime_category,
                        movie_category=movie_category,
                    )
                    stale = [r for r in results if r.state == "stale"]
                    if stale:
                        headers.update(
                            {
                                "X-AniBridge-Catalog-Stale": "true",
                                "X-AniBridge-Catalog-Age": str(
                                    int(max(r.age_s for r in stale))
                                ),
                            }
                        )
                    return rows, total, headers
                raise Unavailable("catalog_changed")
        finally:
            self.active -= 1
