"""Private validated canonical episode hints; cache reuse never guesses numbering."""

from collections import Counter

from catalog_core.identity import search_key

from .episode_matching import infer_seasons, source_keys
from .mapping import CanonicalEpisode
from .state import State
from .transactions import atomic

TTL = 604800
MISSING_RECHECK = 1800


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
    # Multiple canonical episodes with one normalized title are ambiguous,
    # including duplicate source rows. Do not silently pick the last number.
    for episode in episodes:
        key = search_key(episode.title)
        if not key:
            continue
        db.execute(
            "INSERT INTO canonical_hint VALUES(?,?,?,?) ON CONFLICT(title_id,season,title_key) DO UPDATE SET episode=NULL",
            (tid, episode.season, key, episode.episode),
        )


def missing(state: State, tid: str) -> bool:
    return (
        state.db.execute(
            "SELECT 1 FROM entity e JOIN canonical_title c ON c.title_id=e.title_id "
            "WHERE e.title_id=? AND e.kind='episode' AND c.namespace='tvdb' AND e.display_title IS NOT NULL "
            "AND NOT EXISTS(SELECT 1 FROM canonical_episode p WHERE p.mapping_id=c.mapping_id AND p.entity_id=e.entity_id) LIMIT 1",
            (tid,),
        ).fetchone()
        is not None
    )


def apply(state: State, tid: str, checked_at: int) -> str:
    outcome = "matched"
    inferred = infer_seasons(state, tid)
    entities = state.db.execute(
        "SELECT entity_id,native_season,display_title FROM entity WHERE title_id=? AND kind='episode'",
        (tid,),
    ).fetchall()
    keys = {}
    for eid, native, name in entities:
        names = ([name] if name else []) + [
            row[0]
            for row in state.db.execute(
                "SELECT display_title FROM entity_alias WHERE entity_id=?", (eid,)
            )
        ]
        keys[eid] = {
            key for title in names for key in source_keys(title, state.provider) if key
        }
    counts = Counter(key for values in keys.values() for key in values)
    observed_seasons = {}
    for eid, native, _ in entities:
        seasons = observed_seasons.setdefault(native, set())
        for key in keys[eid]:
            hints = state.db.execute(
                "SELECT season,episode FROM canonical_hint WHERE title_id=? AND title_key=? LIMIT 2",
                (tid, key),
            ).fetchall()
            if len(hints) == 1 and hints[0][1] is not None:
                seasons.add(hints[0][0])
    for mid, namespace, external in state.db.execute(
        "SELECT mapping_id,namespace,external_id FROM canonical_title WHERE title_id=? AND namespace='tvdb'",
        (tid,),
    ):
        for eid, native, name in entities:
            season = state.db.execute(
                "SELECT canonical_season FROM season_correspondence WHERE title_id=? AND namespace=? AND external_id=? AND native_season=?",
                (tid, namespace, external, native),
            ).fetchone()
            if season is None and len(observed_seasons[native]) > 1:
                continue
            proven = season[0] if season else inferred.get(native)
            candidates = set()
            ambiguous = False
            for key in keys[eid]:
                hints = state.db.execute(
                    "SELECT season,episode FROM canonical_hint WHERE title_id=? AND title_key=?"
                    + (" AND season=?" if proven is not None else "")
                    + " LIMIT 2",
                    (tid, key, proven) if proven is not None else (tid, key),
                ).fetchall()
                if not hints:
                    continue
                if counts[key] != 1 or len(hints) != 1 or hints[0][1] is None:
                    ambiguous = True
                else:
                    candidates.add(tuple(hints[0]))
            # A unique name in the entire canonical descriptor proves its own
            # coordinates. Native numbers never enter this correspondence.
            if ambiguous or len(candidates) != 1:
                continue
            canonical_season, episode = next(iter(candidates))
            previous = state.db.execute(
                "SELECT season,episode FROM canonical_episode WHERE mapping_id=? AND entity_id=?",
                (mid, eid),
            ).fetchone()
            occupied = state.db.execute(
                "SELECT entity_id FROM canonical_episode WHERE mapping_id=? AND season=? AND episode=?",
                (mid, canonical_season, episode),
            ).fetchone()
            if (
                previous
                and tuple(previous) != (canonical_season, episode)
                or occupied
                and occupied[0] != eid
            ):
                outcome = "conflict"
                continue
            state.db.execute(
                "INSERT INTO canonical_episode VALUES(?,?,?,?,NULL,'exact_title',?) ON CONFLICT(mapping_id,season,episode) DO UPDATE SET checked_at=excluded.checked_at",
                (mid, eid, canonical_season, episode, checked_at),
            )
    return outcome


def reuse(state: State, tid: str, digest: str, matcher: str, now: int) -> bool:
    row = state.db.execute(
        "SELECT * FROM canonical_cache WHERE title_id=?", (tid,)
    ).fetchone()
    if (
        row is None
        or row["input_hash"] != digest
        or row["matcher"] != matcher
        or now - row["checked_at"] >= TTL
    ):
        return False
    with atomic(state.db):
        outcome = apply(state, tid, row["checked_at"])
        # A valid partial cache match must remain publishable even when the
        # remaining episodes require a source recheck which subsequently fails.
        state.db.execute("UPDATE worker_meta SET dirty=1")
        unresolved = missing(state, tid)
        if unresolved and now - row["checked_at"] >= MISSING_RECHECK:
            return False
        state.db.execute(
            "UPDATE mapping_input SET input_hash=?,matcher=?,checked_at=?,next_due=?,outcome=?,failures=0 WHERE title_id=?",
            (
                digest,
                matcher,
                row["checked_at"],
                min(row["checked_at"] + TTL, now + MISSING_RECHECK)
                if unresolved
                else row["checked_at"] + TTL,
                outcome,
                tid,
            ),
        )
        state.db.execute("UPDATE worker_meta SET dirty=1")
    return True
