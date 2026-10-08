"""Bounded Skyhook enrichment, separate from provider requests and publication.

Only compact verified IDs enter worker state. Missing year, ambiguity, and
unknown season correspondence remain unresolved. Rights filtering is a later,
independent export decision.
"""

import asyncio
import hashlib
import json
import time
from collections import deque
from pathlib import Path

from catalog_core.identity import mapping_id
from catalog_core.json_codec import dumps, require
from catalog_core.providers.transport import Session

from . import canonical_cache
from .canonical_ids import identifiers
from .mapping import CanonicalEpisode, CanonicalTitle, match_title
from .movie_canonical import lookup as movie_lookup
from .state import State
from .transport import fetch

MATCHER = "exact-title-year-3"
ORIGIN = "https://skyhook.sonarr.tv"


def titles(payload: object) -> tuple[CanonicalTitle, ...]:
    require(
        isinstance(payload, list) and len(payload) <= 1000,
        "invalid canonical candidates",
    )
    result = []
    for item in payload:
        require(isinstance(item, dict), "invalid canonical candidate")
        tvdb = item.get("tvdbId")
        name = item.get("title")
        require(
            type(tvdb) is int
            and tvdb > 0
            and isinstance(name, str)
            and len(name.encode()) <= 512,
            "invalid canonical identity",
        )
        year = item.get("year")
        if year is None and isinstance(item.get("firstAired"), str):
            raw = item["firstAired"][:4]
            year = int(raw) if raw.isdecimal() else None
        require(
            year is None or (type(year) is int and 1800 <= year <= 2200),
            "invalid canonical year",
        )
        aliases = item.get("aliases") or []
        require(
            isinstance(aliases, list) and len(aliases) <= 100,
            "invalid canonical aliases",
        )
        names = [name]
        for alias in aliases:
            text = alias.get("title") if isinstance(alias, dict) else alias
            if isinstance(text, str) and len(text.encode()) <= 512:
                names.append(text)
        result.append(CanonicalTitle("tvdb", str(tvdb), tuple(names), year, "series"))
    return tuple(result)


class Enricher:
    def __init__(self, sources: dict, fetcher=fetch, clock=time.time) -> None:
        self.sources, self.fetcher, self.clock = sources, fetcher, clock
        self.sessions = {}
        self.pooled = fetcher is fetch
        self.token = None
        if sources.get("movie") == "tmdb":
            with Path(sources["tmdb_token_file"]).open("rb") as stream:
                raw = stream.read(4097)
            require(len(raw) <= 4096, "TMDb credential too large")
            self.token = raw.decode("ascii").strip()
            require(
                bool(self.token) and not any(c.isspace() for c in self.token),
                "invalid TMDb credential",
            )
        self.starts = deque(maxlen=30)
        self.lock = asyncio.Lock()
        self.matcher = MATCHER + ":" + hashlib.sha256(dumps(sources)).hexdigest()

    async def request(
        self, path: str, query: dict | None = None, *, origin=ORIGIN, bearer=None
    ) -> object:
        now = self.clock()
        while self.starts and self.starts[0] <= now - 60:
            self.starts.popleft()
        require(len(self.starts) < 30, "canonical rate limit")
        self.starts.append(now)
        fetcher = self.fetcher
        if self.pooled:
            if origin not in self.sessions:
                self.sessions[origin] = Session(origin, 1)
            fetcher = self.sessions[origin].fetch
        response = await fetcher(
            origin,
            path,
            query=query,
            body_bytes=8 * 1024**2,
            deadline=30,
            **({"bearer": bearer} if bearer else {}),
        )
        require(response.outcome == "ok", "canonical " + response.outcome)
        return json.loads(response.body)

    async def close(self) -> None:
        for session in self.sessions.values():
            await session.close()

    async def tick(self, state: State, now: int) -> bool:
        kinds = []
        if self.sources.get("tv", "skyhook") != "off":
            kinds.append("series")
        if self.sources.get("movie", "off") == "tmdb":
            kinds.append("movie")
        if not kinds:
            return False
        async with self.lock:
            row = state.db.execute(
                f"SELECT m.*,t.display_title,t.year,t.media_type,s.changed_at FROM mapping_input m JOIN title t USING(title_id) JOIN title_schedule s USING(title_id) WHERE (m.next_due<=? OR m.matcher IS NULL OR m.matcher<>?) AND t.media_type IN ({','.join('?' for _ in kinds)}) ORDER BY m.next_due,m.title_id LIMIT 1",
                (now, self.matcher, *kinds),
            ).fetchone()
            if row is None:
                return False
            names = (
                row["display_title"],
                *(
                    r[0]
                    for r in state.db.execute(
                        "SELECT display_alias FROM alias WHERE title_id=? ORDER BY search_key LIMIT 100",
                        (row["title_id"],),
                    )
                ),
            )
            digest = hashlib.sha256(
                dumps([MATCHER, self.sources, names, row["year"], row["explicit_imdb"]])
            ).hexdigest()
            if row["media_type"] == "series" and canonical_cache.reuse(
                state, row["title_id"], digest, self.matcher, now
            ):
                return True
            # A lookup can use two search terms plus one descriptor. Defer the
            # whole lookup when our own budget is low; this isn't a source failure.
            request_now = self.clock()
            while self.starts and self.starts[0] <= request_now - 60:
                self.starts.popleft()
            if len(self.starts) > 27:
                return False
            outcome, mapped = "not_found", None
            failures = row["failures"]
            try:
                if row["media_type"] == "movie":
                    mapped, details = await movie_lookup(
                        self.request, row, names, self.token
                    )
                    if mapped:
                        outcome = "matched"
                else:
                    # Two terms at most, then one series fetch. No episode request loop.
                    candidates = []
                    prior = state.db.execute(
                        "SELECT external_id,evidence FROM canonical_title WHERE title_id=? AND namespace='tvdb'",
                        (row["title_id"],),
                    ).fetchone()
                    if (
                        prior
                        and row["input_hash"] == digest
                        and row["matcher"] == self.matcher
                    ):
                        mapped = (
                            CanonicalTitle(
                                "tvdb", prior[0], names, row["year"], "series"
                            ),
                            prior[1],
                        )
                    elif row["explicit_imdb"]:
                        payload = await self.request(
                            "/v1/tvdb/search/en/",
                            {"term": "imdb:" + row["explicit_imdb"]},
                        )
                        require(isinstance(payload, list), "invalid canonical search")
                        exact = [
                            item
                            for item in payload
                            if isinstance(item, dict)
                            and item.get("imdbId") == row["explicit_imdb"]
                        ]
                        parsed = titles(exact)
                        mapped = (
                            (parsed[0], "explicit_id") if len(parsed) == 1 else None
                        )
                    elif row["year"] is not None:
                        for name in names[:2]:
                            candidates.extend(
                                titles(
                                    await self.request(
                                        "/v1/tvdb/search/en/", {"term": name}
                                    )
                                )
                            )
                        mapped = match_title(
                            names, row["year"], row["media_type"], tuple(candidates)
                        )
                    if mapped:
                        candidate, evidence = mapped
                        details = await self.request(
                            "/v1/tvdb/shows/en/" + candidate.external_id
                        )
                        require(
                            isinstance(details, dict)
                            and str(details.get("tvdbId")) == candidate.external_id,
                            "canonical ID mismatch",
                        )
                        if row["explicit_imdb"]:
                            require(
                                details.get("imdbId") == row["explicit_imdb"],
                                "canonical IMDb mismatch",
                            )
                        outcome = "matched"
                if mapped:
                    compact_ids = identifiers(
                        mapped[0], details, row["media_type"] == "movie"
                    )
                failures = 0
            except ValueError, OSError, TimeoutError:
                mapped, outcome, failures = None, "source_failure", failures + 1
            delay = (
                (300, 1800, 7200, 21600)[min(failures - 1, 3)]
                if failures
                else (604800 if row["changed_at"] > now - 2592000 else 2592000)
                if mapped
                else 86400
            )
            with state.db:
                if mapped:
                    candidate, evidence = mapped
                    # Never silently replace a different previously accepted mapping.
                    previous = state.db.execute(
                        "SELECT namespace,external_id FROM canonical_title WHERE title_id=?",
                        (row["title_id"],),
                    ).fetchall()
                    if any(
                        r[0] in compact_ids and compact_ids[r[0]] != r[1]
                        for r in previous
                    ):
                        outcome = "conflict"
                    else:
                        for namespace, external_id in compact_ids.items():
                            state.db.execute(
                                "INSERT INTO canonical_title VALUES(?,?,?,?,?,?,?) ON CONFLICT(mapping_id) DO UPDATE SET checked_at=excluded.checked_at",
                                (
                                    mapping_id(
                                        state.provider,
                                        row["title_id"],
                                        namespace,
                                        external_id,
                                    ),
                                    row["title_id"],
                                    namespace,
                                    external_id,
                                    "tmdb-v3"
                                    if row["media_type"] == "movie"
                                    else "skyhook-v1",
                                    evidence
                                    if namespace == candidate.namespace
                                    else "explicit_id",
                                    now,
                                ),
                            )
                        episodes = (
                            (details.get("episodes") or [])
                            if row["media_type"] == "series"
                            else []
                        )
                        require(
                            isinstance(episodes, list) and len(episodes) <= 100000,
                            "invalid canonical episode list",
                        )
                        canonical_episodes = []
                        for episode in episodes:
                            require(
                                isinstance(episode, dict), "invalid canonical episode"
                            )
                            season, number, name = (
                                episode.get("seasonNumber"),
                                episode.get("episodeNumber"),
                                episode.get("title"),
                            )
                            if (
                                type(season) is int
                                and season >= 0
                                and type(number) is int
                                and number > 0
                                and isinstance(name, str)
                                and len(name.encode()) <= 512
                            ):
                                canonical_episodes.append(
                                    CanonicalEpisode(season, number, name)
                                )
                        if row["media_type"] == "series":
                            canonical_cache.store(
                                state,
                                row["title_id"],
                                digest,
                                self.matcher,
                                now,
                                canonical_episodes,
                            )
                            outcome = canonical_cache.apply(state, row["title_id"], now)
                        state.db.execute("UPDATE worker_meta SET dirty=1")
                if (
                    mapped
                    and row["media_type"] == "series"
                    and canonical_cache.missing(state, row["title_id"])
                ):
                    delay = min(delay, canonical_cache.MISSING_RECHECK)
                state.db.execute(
                    "UPDATE mapping_input SET input_hash=?,matcher=?,checked_at=?,next_due=?,outcome=?,failures=? WHERE title_id=?",
                    (
                        digest,
                        self.matcher,
                        now,
                        now + delay,
                        outcome,
                        failures,
                        row["title_id"],
                    ),
                )
            return True
