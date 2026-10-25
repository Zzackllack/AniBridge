"""Bounded Skyhook enrichment, separate from provider requests and publication.

Only compact verified IDs enter worker state. Missing year, ambiguity, and
unknown season correspondence remain unresolved. Rights filtering is a later,
independent export decision.
"""

import asyncio
import hashlib
import json
import math
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path

from catalog_core.identity import mapping_id, search_key
from catalog_core.json_codec import dumps, integer, require
from catalog_core.providers.transport import AdmissionDeferred, Fetch, Session

from . import canonical_cache, descriptors, parent_evidence
from .canonical_failures import CanonicalUnavailable, Failure, request_phase, verify
from .canonical_ids import identifiers
from .mapping import CanonicalTitle, match_title
from .movie_canonical import lookup as movie_lookup
from .state import State
from .transport import fetch

MATCHER = "exact-title-year-3"
ORIGIN = "https://skyhook.sonarr.tv"


def search_terms(names: tuple[str, ...]) -> tuple[str, ...]:
    """Keep two distinct terms without changing the historical parent digest."""
    seen, result = set(), []
    for name in names:
        key = search_key(name)
        if key and key not in seen:
            result.append(name)
            seen.add(key)
        if len(result) == 2:
            break
    return tuple(result)


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
        aliases = item.get("aliases") or item.get("alternativeTitles") or []
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
    def __init__(
        self,
        sources: dict,
        fetcher=fetch,
        clock=time.time,
        *,
        states: list[State] | None = None,
        requests_per_minute: int = 30,
        on_fetch: Callable[[str, Fetch], None] | None = None,
        on_failure: Callable[[str, str, Failure], None] | None = None,
    ) -> None:
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
        self.requests_per_minute = integer(requests_per_minute, 4, 120)
        self.starts = deque(maxlen=self.requests_per_minute)
        self.on_fetch = on_fetch
        self.on_failure = on_failure
        self.failure_phase = "search"
        self.last_failure: Failure | None = None
        self.lock = asyncio.Lock()
        self.parent_sources = {
            key: value for key, value in sources.items() if key != "episode_languages"
        }
        self.matcher = (
            MATCHER + ":" + hashlib.sha256(dumps(self.parent_sources)).hexdigest()
        )
        if sources.get("episode_languages"):
            self.matcher += ":" + ",".join(sources["episode_languages"])
        self.states = list(states or [])
        self.current_state = None
        self.last_work = "idle"

    def request_count(self, now: float) -> int:
        while self.starts and self.starts[0] <= now - 60:
            self.starts.popleft()
        durable = sum(
            state.db.execute(
                "SELECT count(*) FROM canonical_request_start WHERE at>?", (now - 60,)
            ).fetchone()[0]
            for state in self.states
        )
        return max(len(self.starts), durable)

    def admit_request(self) -> None:
        now = self.clock()
        if self.request_count(now) >= self.requests_per_minute:
            raise AdmissionDeferred(60)
        self.starts.append(now)
        if self.current_state is not None:
            with self.current_state.db:
                self.current_state.db.execute(
                    "DELETE FROM canonical_request_start WHERE at<=?", (now - 60,)
                )
                self.current_state.db.execute(
                    "INSERT INTO canonical_request_start VALUES(?)", (math.ceil(now),)
                )

    async def request(
        self, path: str, query: dict | None = None, *, origin=ORIGIN, bearer=None
    ) -> object:
        self.failure_phase = request_phase(path)
        self.admit_request()
        first_hop = True

        async def before_request() -> None:
            nonlocal first_hop
            if first_hop:
                first_hop = False
            else:
                self.admit_request()

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
            before_request=before_request,
            **({"bearer": bearer} if bearer else {}),
        )
        if self.on_fetch is not None and self.current_state is not None:
            self.on_fetch(self.current_state.provider, response)
        if response.outcome != "ok":
            raise CanonicalUnavailable(
                response.retry_after, reason=response.outcome, status=response.status
            )
        try:
            return json.loads(response.body)
        except (ValueError, UnicodeError) as exc:
            raise CanonicalUnavailable(
                None, reason="invalid_json", status=response.status
            ) from exc

    async def close(self) -> None:
        for session in self.sessions.values():
            await session.close()

    async def imdb_candidate(
        self, imdb: str, names: tuple[str, ...]
    ) -> tuple[CanonicalTitle, str] | None:
        # Skyhook's current imdb: search can return an empty list while a title
        # search returns that exact IMDb association. One bounded fallback is
        # safe only with the same explicit ID, rechecked on the descriptor below.
        for term in ("imdb:" + imdb, names[0]):
            payload = await self.request(
                "/v2/tvdb/search", {"term": term, "language": "eng"}
            )
            require(
                isinstance(payload, list) and len(payload) <= 1000,
                "invalid canonical search",
            )
            exact = [
                item
                for item in payload
                if isinstance(item, dict) and item.get("imdbId") == imdb
            ]
            parsed = titles(exact)
            if len(parsed) == 1:
                return parsed[0], "explicit_id"
            if parsed:
                return None
        return None

    async def tick(
        self, state: State, now: int, *, title_id: str | None = None
    ) -> bool:
        kinds = []
        if self.sources.get("tv", "skyhook") != "off":
            kinds.append("series")
        if self.sources.get("movie", "off") == "tmdb":
            kinds.append("movie")
        if not kinds:
            return False
        async with self.lock:
            if state not in self.states:
                self.states.append(state)
            self.current_state = state
            self.last_work = "idle"
            self.last_failure = None
            self.failure_phase = "cache"
            slot = (
                state.db.execute("SELECT slot FROM canonical_scheduler").fetchone()[0]
                % 5
            )
            # Reserve opportunities for old work and real retries even during a
            # growing first-pass queue. The tie-break stays durable and bounded.
            priority = (
                "m.checked_at IS NULL",
                "m.checked_at IS NULL",
                "m.next_due=0 AND m.checked_at IS NOT NULL",
                "m.failures>0",
                "m.checked_at IS NOT NULL AND m.next_due>0 AND m.failures=0",
            )[slot]
            row = state.db.execute(
                f"SELECT m.*,t.display_title,t.year,t.media_type,s.changed_at FROM mapping_input m JOIN title t USING(title_id) JOIN title_schedule s USING(title_id) WHERE (m.next_due<=? OR (m.failures=0 AND (m.matcher IS NULL OR m.matcher<>? OR (EXISTS(SELECT 1 FROM canonical_cache c WHERE c.title_id=m.title_id) AND NOT EXISTS(SELECT 1 FROM matching_replay r WHERE r.title_id=m.title_id AND r.matcher=?))))) AND t.media_type IN ({','.join('?' for _ in kinds)}) AND (? IS NULL OR m.title_id=?) ORDER BY NOT ({priority}),m.next_due,m.title_id LIMIT 1",
                (
                    now,
                    self.matcher,
                    canonical_cache.EPISODE_MATCHER,
                    *kinds,
                    title_id,
                    title_id,
                ),
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
                dumps(
                    [
                        MATCHER,
                        self.parent_sources,
                        names,
                        row["year"],
                        row["explicit_imdb"],
                    ]
                )
            ).hexdigest()
            if row["media_type"] == "series" and canonical_cache.reuse(
                state,
                row["title_id"],
                digest,
                self.matcher,
                now,
                languages=tuple(self.sources.get("episode_languages", [])),
            ):
                with state.db:
                    state.db.execute("UPDATE canonical_scheduler SET slot=(slot+1)%5")
                replay = state.db.execute(
                    "SELECT examined_at FROM matching_replay WHERE title_id=?",
                    (row["title_id"],),
                ).fetchone()
                self.last_work = (
                    "local_rematch" if replay and replay[0] == now else "unchanged"
                )
                return True
            # A lookup can use two search terms plus one descriptor. Defer the
            # whole lookup when our own budget is low; this isn't a source failure.
            request_now = self.clock()
            if self.request_count(request_now) > self.requests_per_minute - 4:
                self.last_work = "admission_deferred"
                return False
            outcome, mapped = "not_found", None
            canonical_episodes = []
            acquired_at = now
            reused_descriptor = False
            failures = row["failures"]
            retry_after = None
            try:
                self.failure_phase = "search"
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
                    reused_parent = bool(prior and row["input_hash"] == digest)
                    if prior and row["input_hash"] == digest:
                        mapped = (
                            CanonicalTitle(
                                "tvdb", prior[0], names, row["year"], "series"
                            ),
                            prior[1],
                        )
                    elif row["explicit_imdb"]:
                        mapped = await self.imdb_candidate(row["explicit_imdb"], names)
                    elif row["year"] is not None:
                        for name in search_terms(names):
                            candidates.extend(
                                titles(
                                    await self.request(
                                        "/v2/tvdb/search",
                                        {"term": name, "language": "eng"},
                                    )
                                )
                            )
                        mapped = match_title(
                            names, row["year"], row["media_type"], tuple(candidates)
                        )
                    if mapped:
                        candidate, evidence = mapped
                        shared = descriptors.cached(
                            self.states,
                            candidate.external_id,
                            now,
                            row["explicit_imdb"],
                            tuple(self.sources.get("episode_languages", [])),
                            newer_than=row["checked_at"] if failures else None,
                        )
                        if shared:
                            details, canonical_episodes, acquired_at, _ = shared
                            reused_descriptor = True
                        else:
                            details = await self.request(
                                "/v2/tvdb/shows/eng/"
                                + candidate.external_id
                                + "/official"
                                if self.sources.get("episode_languages")
                                else "/v1/tvdb/shows/en/" + candidate.external_id
                            )
                        self.failure_phase = "descriptor"
                        verify(
                            isinstance(details, dict)
                            and str(details.get("tvdbId")) == candidate.external_id,
                            "parent_id_mismatch",
                            "canonical ID mismatch",
                        )
                        if (
                            self.sources.get("episode_languages")
                            and not reused_descriptor
                        ):
                            verify(
                                details.get("metadataSource") == "tvdb"
                                and details.get("language") == "eng",
                                "metadata_namespace_mismatch",
                                "canonical descriptor namespace mismatch",
                            )
                        if row["explicit_imdb"]:
                            verify(
                                details.get("imdbId") == row["explicit_imdb"],
                                "parent_imdb_mismatch",
                                "canonical IMDb mismatch",
                            )
                        if not reused_descriptor:
                            canonical_episodes = descriptors.episodes(details)
                            for language in self.sources.get("episode_languages", []):
                                # Sonarr v5's maintained v2 route. Its IDs are
                                # namespaced by metadataSource; never join rows
                                # just because their season/episode numbers agree.
                                translated = await self.request(
                                    "/v2/tvdb/shows/"
                                    + language
                                    + "/"
                                    + candidate.external_id
                                    + "/official"
                                )
                                translated_rows, unavailable = descriptors.translation(
                                    translated, candidate.external_id, language
                                )
                                if unavailable:
                                    details.setdefault(
                                        "_missing_episode_languages", []
                                    ).append(language)
                                canonical_episodes = descriptors.merge(
                                    canonical_episodes, translated_rows
                                )
                            details["_episode_languages"] = self.sources.get(
                                "episode_languages", []
                            )
                        outcome = "matched"
                        self.failure_phase = "parent"
                        # Only a locally compacted shared descriptor carries our
                        # private proof. A remote field named "parent" cannot
                        # override the descriptor's actual year/names/IMDb.
                        parent = (
                            details["parent"]
                            if reused_descriptor
                            else parent_evidence.compact(details)
                        )
                        if not reused_parent:
                            # These names came from a canonical search with this
                            # exact ID, not from our provider/source names. The
                            # descriptor's own year/IDs still win on conflict.
                            parent["names"] = list(
                                dict.fromkeys([*parent["names"], *candidate.titles])
                            )
                        details["parent"] = parent
                        if (
                            parent_evidence.check(
                                state, row["title_id"], candidate.external_id, parent
                            )
                            != "verified"
                        ):
                            with state.db:
                                descriptors.save(
                                    state,
                                    candidate.external_id,
                                    details,
                                    canonical_episodes,
                                    acquired_at,
                                    canonical_cache.TTL,
                                )
                            mapped, outcome = None, "conflict"
                if mapped:
                    self.failure_phase = "identifiers"
                    compact_ids = identifiers(
                        mapped[0], details, row["media_type"] == "movie"
                    )
                failures = 0
            except AdmissionDeferred:
                self.last_work = "admission_deferred"
                return False
            except (ValueError, OSError, TimeoutError) as exc:
                mapped, outcome, failures = None, "source_failure", failures + 1
                retry_after = getattr(exc, "retry_after", None)
                self.last_failure = Failure.from_error(self.failure_phase, exc)
            delay = (
                (300, 1800, 7200, 21600)[min(failures - 1, 3)]
                if failures
                else (604800 if row["changed_at"] > now - 2592000 else 2592000)
                if mapped
                else 86400
            )
            if retry_after is not None:
                delay = max(delay, min(86400, max(1, retry_after)))
            with state.db:
                state.db.execute("UPDATE canonical_scheduler SET slot=(slot+1)%5")
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
                                    # Existing allowlist authority tag is kept;
                                    # compact private evidence records the API.
                                    else "skyhook-v1",
                                    evidence
                                    if namespace == candidate.namespace
                                    else "explicit_id",
                                    now,
                                ),
                            )
                        if row["media_type"] == "series":
                            descriptors.save(
                                state,
                                candidate.external_id,
                                details,
                                canonical_episodes,
                                acquired_at,
                                canonical_cache.refresh_delay(
                                    state, row["title_id"], now
                                ),
                            )
                            canonical_cache.store(
                                state,
                                row["title_id"],
                                digest,
                                self.matcher,
                                acquired_at,
                                canonical_episodes,
                            )
                            outcome = canonical_cache.apply(
                                state, row["title_id"], acquired_at, examined_at=now
                            )
                        state.db.execute("UPDATE worker_meta SET dirty=1")
                if (
                    mapped
                    and row["media_type"] == "series"
                    and canonical_cache.missing(state, row["title_id"])
                ):
                    delay = min(
                        delay,
                        canonical_cache.refresh_delay(state, row["title_id"], now),
                    )
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
            if self.last_failure is not None and self.on_failure is not None:
                self.on_failure(state.provider, row["title_id"], self.last_failure)
            self.last_work = (
                "descriptor_reuse"
                if reused_descriptor
                else "source_failure"
                if failures
                else "examined"
            )
            return True
