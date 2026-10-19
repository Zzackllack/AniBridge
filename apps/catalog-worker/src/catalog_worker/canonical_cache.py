"""Validated descriptors and local correspondence have separate clocks."""

import hashlib
import json
from collections import Counter

from catalog_core.identity import search_key
from catalog_core.json_codec import dumps

from .correspondence import decisions
from .descriptors import CODEC
from .episode_matching import source_keys
from .mapping import CanonicalEpisode
from .parent_evidence import status as parent_status
from .state import State
from .transactions import atomic

TTL = 604800
# An unresolved wording mismatch is not a reason to redownload in 30 minutes.
MISSING_RECHECK = TTL
EPISODE_MATCHER = "unique-name-context-7"


def store(
    state: State,
    tid: str,
    digest: str,
    matcher: str,
    now: int,
    episodes: list[CanonicalEpisode],
) -> None:
    db = state.db
    db.execute("DELETE FROM canonical_cache WHERE title_id=?", (tid,))
    db.execute(
        "INSERT INTO canonical_cache VALUES(?,?,?,?)", (tid, digest, matcher, now)
    )
    for episode in episodes:
        for name in (episode.title, *episode.aliases):
            key = search_key(name)
            if not key:
                continue
            # Repeated translations of the SAME episode aren't ambiguity.
            db.execute(
                "INSERT INTO canonical_hint VALUES(?,?,?,?) ON CONFLICT(title_id,season,title_key) DO UPDATE SET episode=CASE WHEN canonical_hint.episode=excluded.episode THEN excluded.episode ELSE NULL END",
                (tid, episode.season, key, episode.episode),
            )
        if episode.external_id:
            db.execute(
                "INSERT INTO canonical_hint_identity VALUES(?,?,?,?) ON CONFLICT(title_id,season,episode) DO NOTHING",
                (tid, episode.season, episode.episode, episode.external_id),
            )


def fingerprints(state: State, tid: str) -> tuple[str, str]:
    """Hash relevant evidence only, not fetch times or language-only changes."""
    db = state.db
    source = hashlib.sha256()
    descriptor = hashlib.sha256()
    queries = (
        (source, "SELECT display_title,year FROM title WHERE title_id=?"),
        (source, "SELECT explicit_imdb FROM mapping_input WHERE title_id=?"),
        (source, "SELECT search_key FROM alias WHERE title_id=? ORDER BY search_key"),
        (
            descriptor,
            "SELECT d.content_hash FROM canonical_descriptor d JOIN canonical_title t ON t.external_id=d.external_id WHERE t.title_id=? AND t.namespace='tvdb'",
        ),
        (
            source,
            "SELECT entity_id,native_season,display_title FROM entity WHERE title_id=? AND kind='episode' ORDER BY entity_id",
        ),
        (
            source,
            "SELECT a.entity_id,a.title_key FROM entity_alias a JOIN entity e USING(entity_id) WHERE e.title_id=? ORDER BY a.entity_id,a.title_key",
        ),
        (
            source,
            "SELECT namespace,external_id,evidence FROM canonical_title WHERE title_id=? ORDER BY namespace,external_id",
        ),
        (
            source,
            "SELECT namespace,external_id,native_season,canonical_season,evidence FROM season_correspondence WHERE title_id=? ORDER BY namespace,external_id,native_season",
        ),
        (
            descriptor,
            "SELECT season,title_key,episode FROM canonical_hint WHERE title_id=? ORDER BY season,title_key",
        ),
        (
            descriptor,
            "SELECT season,episode,external_id FROM canonical_hint_identity WHERE title_id=? ORDER BY season,episode",
        ),
    )
    for hasher, query in queries:
        hasher.update(b"\x00")
        for row in db.execute(query, (tid,)):
            hasher.update(dumps(tuple(row)))
            hasher.update(b"\n")
    return source.hexdigest(), descriptor.hexdigest()


def missing(state: State, tid: str) -> bool:
    return (
        state.db.execute(
            "SELECT 1 FROM entity e JOIN canonical_title c ON c.title_id=e.title_id WHERE e.title_id=? AND e.kind='episode' AND c.namespace='tvdb' AND NOT EXISTS(SELECT 1 FROM canonical_episode p WHERE p.mapping_id=c.mapping_id AND p.entity_id=e.entity_id) LIMIT 1",
            (tid,),
        ).fetchone()
        is not None
    )


def refresh_delay(state: State, tid: str, now: int) -> int:
    """Newly observed named episodes await canonical arrivals; old wording doesn't.

    Even if every partial series were new, one descriptor/day fits the retained
    cap for this ledger. Freshness eligibility isn't a whole-provider SLA.
    """
    recent = state.db.execute(
        "SELECT e.entity_id,e.display_title FROM entity e WHERE e.title_id=? AND e.kind='episode' AND EXISTS(SELECT 1 FROM release r WHERE r.entity_id=e.entity_id AND r.first_seen_at>?) AND NOT EXISTS(SELECT 1 FROM canonical_episode p WHERE p.entity_id=e.entity_id) LIMIT 100000",
        (tid, now - TTL),
    )
    for eid, name in recent:
        names = ([name] if name else []) + [
            r[0]
            for r in state.db.execute(
                "SELECT display_title FROM entity_alias WHERE entity_id=?", (eid,)
            )
        ]
        if any(key for name in names for key in source_keys(name, state.provider)):
            return 86400
    return TTL


def apply(
    state: State, tid: str, checked_at: int, *, examined_at: int | None = None
) -> str:
    """Rematch only changed inputs; preserve all previously accepted identities."""
    source, descriptor = fingerprints(state, tid)
    previous = state.db.execute(
        "SELECT * FROM matching_replay WHERE title_id=?", (tid,)
    ).fetchone()
    if previous and (
        previous["source_hash"],
        previous["descriptor_hash"],
        previous["matcher"],
    ) == (source, descriptor, EPISODE_MATCHER):
        return "unchanged"
    counts = Counter()
    outcome, added = "matched", 0
    for decision in decisions(state, tid, contextual=True):
        counts[decision.reason] += 1
        if decision.reason.endswith("conflict"):
            outcome = "conflict"
        if decision.reason != "accepted":
            continue
        season, episode = decision.coordinate
        identity = state.db.execute(
            "SELECT external_id FROM canonical_hint_identity WHERE title_id=? AND season=? AND episode=?",
            (tid, season, episode),
        ).fetchone()
        state.db.execute(
            "INSERT INTO canonical_episode VALUES(?,?,?,?,?,'exact_title',?) ON CONFLICT(mapping_id,season,episode) DO NOTHING",
            (
                decision.mapping_id,
                decision.entity_id,
                season,
                episode,
                identity[0] if identity else None,
                checked_at,
            ),
        )
        added += 1
    state.db.execute(
        "INSERT INTO matching_replay VALUES(?,?,?,?,?,?) ON CONFLICT(title_id) DO UPDATE SET source_hash=excluded.source_hash,descriptor_hash=excluded.descriptor_hash,matcher=excluded.matcher,examined_at=excluded.examined_at,counts=excluded.counts",
        (
            tid,
            source,
            descriptor,
            EPISODE_MATCHER,
            examined_at if examined_at is not None else checked_at,
            json.dumps(dict(counts), sort_keys=True),
        ),
    )
    if added:
        state.db.execute("UPDATE worker_meta SET dirty=1")
    return outcome


def reuse(
    state: State,
    tid: str,
    digest: str,
    matcher: str,
    now: int,
    *,
    languages: tuple[str, ...] = (),
) -> bool:
    row = state.db.execute(
        "SELECT * FROM canonical_cache WHERE title_id=?", (tid,)
    ).fetchone()
    if row is None or row["input_hash"] != digest:
        return False
    with atomic(state.db):
        outcome = apply(state, tid, row["checked_at"], examined_at=now)
        parent = state.db.execute(
            "SELECT external_id,evidence FROM canonical_title WHERE title_id=? AND namespace='tvdb'",
            (tid,),
        ).fetchone()
        if (
            parent
            and parent_status(state, tid, *parent) == "waiting_parent_verification"
        ):
            return False
        if parent and languages:
            evidence = state.db.execute(
                "SELECT json_extract(payload,'$.languages'),json_extract(payload,'$.codec') FROM canonical_descriptor WHERE external_id=?",
                (parent[0],),
            ).fetchone()
            if (
                not evidence
                or evidence[1] != CODEC
                or not set(languages).issubset(json.loads(evidence[0] or "[]"))
            ):
                return False
        delay = refresh_delay(state, tid, now)
        if now - row["checked_at"] >= delay:
            return False
        # Local rematching must not erase a real remote failure/backoff deadline.
        state.db.execute(
            "UPDATE mapping_input SET matcher=?,next_due=CASE WHEN failures>0 THEN next_due ELSE ? END,outcome=CASE WHEN failures>0 OR ?='unchanged' THEN outcome ELSE ? END WHERE title_id=?",
            (matcher, row["checked_at"] + delay, outcome, outcome, tid),
        )
    return True
