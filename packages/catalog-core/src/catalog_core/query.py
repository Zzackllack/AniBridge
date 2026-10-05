"""Bounded indexed snapshot queries. This module has no HTTP client."""

import re
import sqlite3
import time
from dataclasses import dataclass

from catalog_core import identity
from catalog_core.json_codec import require

LANGUAGES = {
    "de-dub": "German Dub",
    "en-dub": "English Dub",
    "de-sub": "German Sub",
    "en-sub": "English Sub",
}
TORZNAB = "http://torznab.com/schemas/2015/feed"
NEWZNAB = "http://www.newznab.com/DTD/2010/feeds/attributes/"


def number(
    params: dict[str, str], key: str, default: int | None, low: int, high: int
) -> int | None:
    value = params.get(key)
    if value is None:
        return default
    require(re.fullmatch(r"[0-9]+", value) is not None, "invalid_request")
    result = int(value)
    require(low <= result <= high, "invalid_request")
    return result


@dataclass(frozen=True)
class Query:
    mode: str
    text: str
    ids: dict[str, str]
    season: int | None
    episode: int | None
    year: int | None
    limit: int
    offset: int
    maxage: int
    categories: frozenset[int] | None

    @property
    def recent(self) -> bool:
        return (
            not self.text
            and not self.ids
            and self.season is None
            and self.episode is None
        )


def parse(params: dict[str, str]) -> Query:
    mode = params.get("t", "")
    if mode == "movie-search":
        mode = "movie"
    require(mode in ("search", "tvsearch", "movie"), "unsupported_function")
    require(not any(key in params for key in ("rid", "tvmazeid")), "unsupported_id")
    ids = {}
    for key, namespace in (
        ("tvdbid", "tvdb"),
        ("tmdbid", "tmdb-movie" if mode == "movie" else "tmdb-tv"),
        ("imdbid", "imdb"),
    ):
        if key in params:
            value = params[key]
            # Torznab clients such as Radarr strip IMDb's "tt" prefix on the
            # wire. Keep the shared identities/magnet contract canonical.
            if namespace == "imdb" and re.fullmatch(r"[0-9]{7,12}", value):
                value = "tt" + value
            identity.validate_external_id(namespace, value)
            require(mode != "movie" or namespace != "tvdb", "unsupported_id")
            ids[namespace] = value
    text = identity.search_key(params.get("q", ""))
    require(len(text.encode()) <= 512, "invalid_request")
    season = number(params, "season", None, 0, 2**31 - 1)
    episode = number(params, "ep", None, 0, 2**31 - 1)
    require(
        (season is None and episode is None) or bool(text or ids), "invalid_request"
    )
    require(episode in (None, 0) or season is not None, "invalid_request")
    require(mode != "movie" or season is None and episode is None, "invalid_request")
    categories = None
    if "cat" in params:
        require(
            re.fullmatch(r"[0-9]+(?:,[0-9]+)*", params["cat"]) is not None,
            "invalid_request",
        )
        categories = frozenset(int(value) for value in params["cat"].split(","))
    return Query(
        mode,
        text,
        ids,
        season,
        episode or None,
        number(params, "year", None, 1800, 2200),
        number(params, "limit", 100, 1, 100),
        number(params, "offset", 0, 0, 10000),
        number(params, "maxage", 30, 1, 30),
        categories,
    )


def candidates(db: sqlite3.Connection, text: str) -> list[str]:
    # Search keys contain alphanumerics and spaces only, so SQL wildcards from
    # user input cannot survive normalization.
    rows = db.execute(
        "SELECT title_id FROM title WHERE search_key LIKE ? UNION SELECT title_id FROM alias WHERE search_key LIKE ? LIMIT 201",
        (text + "%", text + "%"),
    ).fetchall()
    require(len(rows) <= 200, "query_too_broad")
    return [r[0] for r in rows]


def query(
    store,
    request: Query,
    *,
    now: int,
    modes: tuple[str, ...] = ("download",),
    languages: dict[str, set[str]] | None = None,
    anime_category: int = 5070,
    movie_category: int = 2000,
    mapping_view=None,
    title_ids: set[str] | None = None,
    entity_ids: set[str] | None = None,
) -> tuple[list[dict], int, dict[str, str]]:
    deadline = time.monotonic() + 2
    total, results = 0, []
    headers = {}
    with store.acquire() as (catalogs, private):
        require(bool(catalogs), "catalog_unavailable")
        missing = set(store.providers) - catalogs.keys()
        if missing:
            headers.update(
                {
                    "X-AniBridge-Catalog-Partial": "true",
                    "X-AniBridge-Catalog-Unavailable": ",".join(sorted(missing)),
                }
            )
        from catalog_core.compact import oldest_release, release_from

        for index, (provider, (db, metadata)) in enumerate(catalogs.items()):
            if mapping_view is not None:
                db = mapping_view(private, db, provider, index, now=now)
            db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            where, args = [], []
            if request.mode == "movie":
                where.append("e.kind='movie'")
            elif request.mode == "tvsearch":
                where.append("e.kind='episode'")
                if not request.recent:
                    where.append("ce.entity_id IS NOT NULL")
            selected_titles = (
                set(candidates(db, request.text)) if request.text else None
            )
            if title_ids is not None:
                selected_titles = (
                    title_ids
                    if selected_titles is None
                    else selected_titles & title_ids
                )
            for namespace, value in request.ids.items():
                matches = {
                    row[0]
                    for row in db.execute(
                        "SELECT title_id FROM canonical_title WHERE namespace=? AND external_id=? LIMIT 2",
                        (namespace, value),
                    )
                }
                # More than one provider title for the same ID is unresolved.
                if len(matches) != 1:
                    selected_titles = set()
                    break
                selected_titles = (
                    matches if selected_titles is None else selected_titles & matches
                )
            if selected_titles is not None:
                if not selected_titles:
                    continue
                where.append(
                    f"t.title_id IN ({','.join('?' for _ in selected_titles)})"
                )
                args.extend(sorted(selected_titles))
            if entity_ids is not None:
                if not entity_ids:
                    continue
                where.append(f"e.entity_id IN ({','.join('?' for _ in entity_ids)})")
                args.extend(sorted(entity_ids))
            if request.season is not None:
                where.append("ce.season=?")
                args.append(request.season)
            if request.episode is not None:
                where.append("ce.episode=?")
                args.append(request.episode)
            if request.year is not None:
                where.append("t.year=?")
                args.append(request.year)
            if request.recent and title_ids is None:
                where.append("r.first_seen_at>=?")
                args.append(now - request.maxage * 86400)
            allowed = (languages or {}).get(provider, set(LANGUAGES))
            if not allowed:
                continue
            if allowed != set(LANGUAGES):
                where.append(f"r.language IN ({','.join('?' for _ in allowed)})")
                args.extend(sorted(allowed))
            category_expr = f"CASE WHEN e.kind='movie' THEN {int(movie_category)} WHEN '{provider}'='aniworld.to' THEN {int(anime_category)} ELSE 5000 END"
            if request.categories is not None:
                where.append(
                    f"({category_expr}) IN ({','.join('?' for _ in request.categories)})"
                )
                args.extend(sorted(request.categories))
            join = """FROM release r JOIN entity e USING(entity_id) JOIN title t USING(title_id)
                LEFT JOIN canonical_title ct ON ct.mapping_id=(SELECT c.mapping_id FROM canonical_title c
                    WHERE c.title_id=t.title_id ORDER BY CASE c.namespace WHEN 'tvdb' THEN 0 WHEN 'tmdb-tv' THEN 1 ELSE 2 END,c.namespace LIMIT 1)
                LEFT JOIN canonical_episode ce ON ce.mapping_id=ct.mapping_id AND ce.entity_id=e.entity_id"""
            # TMDB episode coordinates can differ from TVDB. A TMDB-only
            # request must use its explicit episode map, including local fixes.
            if "tmdb-tv" in request.ids and "tvdb" not in request.ids:
                join = join.replace(
                    "WHEN 'tvdb' THEN 0 WHEN 'tmdb-tv' THEN 1",
                    "WHEN 'tmdb-tv' THEN 0 WHEN 'tvdb' THEN 1",
                )
            if metadata["catalog_schema_version"] == 2 and not hasattr(db, "alias"):
                from catalog_core.compact import query_joins

                join = query_joins(join)
                where = [
                    term.replace("ce.entity_id", "ce.entity_key") for term in where
                ]
            condition = " WHERE " + " AND ".join(where) if where else ""
            needs_episode_map = (
                (request.mode == "tvsearch" and not request.recent)
                or request.season is not None
                or request.episode is not None
            )
            if needs_episode_map:
                count_join = join
            else:
                count_join = "FROM release r"
                if any("e." in term or "t." in term for term in where):
                    count_join += " JOIN entity e USING(entity_id)"
                if any("t." in term for term in where):
                    count_join += " JOIN title t USING(title_id)"
            # Bootstrap RSS often contains every release. The minimum lookup is
            # indexed, and the signed row count was verified on activation; do
            # not scan millions of identical recent timestamps for each poll.
            oldest = None
            if where == ["r.first_seen_at>=?"]:
                oldest = (
                    db.oldest_release()
                    if hasattr(db, "oldest_release")
                    else oldest_release(db, metadata["catalog_schema_version"])
                )
            if oldest is not None and oldest >= args[0]:
                count = (
                    db.recent_count(metadata["counts"]["release"], args[0])
                    if getattr(db, "observations", False)
                    else metadata["counts"]["release"]
                )
            else:
                count = db.execute(
                    "SELECT count(*) " + count_join + condition, args
                ).fetchone()[0]
            total += count * len(modes)
            if request.recent:
                # Force the release-order index so SQLite does not sort/join the
                # entire recent catalog before returning its first 100 rows.
                join = join.replace(
                    "FROM release r",
                    release_from(
                        1
                        if hasattr(db, "alias")
                        else metadata["catalog_schema_version"],
                        ordered=True,
                    ),
                )
            select = """SELECT r.*, e.title_id,e.kind,e.native_season,e.native_episode,e.path,
                e.identity_anchor AS entity_anchor,t.identity_anchor AS title_anchor,t.slug,t.display_title,t.year,
                ct.namespace,ct.external_id,ce.season,ce.episode """
            rows = db.execute(
                select
                + join
                + condition
                + " ORDER BY r.first_seen_at DESC,r.release_id ASC LIMIT ?",
                [*args, request.offset + request.limit],
            )
            for row in rows:
                record = dict(row)
                record.update(
                    provider=provider,
                    snapshot_digest=metadata["artifact"]["sqlite_sha256"],
                    category=movie_category
                    if record["kind"] == "movie"
                    else anime_category
                    if provider == "aniworld.to"
                    else 5000,
                )
                for mode in modes:
                    results.append(dict(record, mode=mode))
            require(time.monotonic() <= deadline, "query_deadline")
    results.sort(key=lambda r: (-r["first_seen_at"], r["release_id"], r["mode"]))
    selected = results[request.offset : request.offset + request.limit]
    if request.ids and not total:
        headers["X-AniBridge-Mapping"] = "unresolved"
    elif any(r["kind"] == "episode" and r["season"] is None for r in selected):
        headers["X-AniBridge-Mapping"] = "partial"
    return selected, total, headers
