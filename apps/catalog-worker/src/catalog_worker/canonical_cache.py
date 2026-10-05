"""Private validated canonical episode hints; cache reuse never guesses numbering."""

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
        db.execute(
            "INSERT INTO canonical_hint VALUES(?,?,?,?) ON CONFLICT(title_id,season,title_key) DO UPDATE SET episode=NULL",
            (tid, episode.season, search_key(episode.title), episode.episode),
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
    # Use the same Unicode normalizer and per-entity primary-key probes; an
    # entity×full-series hint join would needlessly multiply every refresh.
    for mapping in state.db.execute(
        "SELECT mapping_id,namespace,external_id FROM canonical_title WHERE title_id=? AND namespace='tvdb'",
        (tid,),
    ):
        mid, namespace, external = mapping
        for entity in state.db.execute(
            "SELECT entity_id,native_season,display_title FROM entity WHERE title_id=? AND kind='episode'",
            (tid,),
        ):
            eid, native, name = entity
            if not name:
                continue
            season = state.db.execute(
                "SELECT canonical_season FROM season_correspondence WHERE title_id=? AND namespace=? AND external_id=? AND native_season=?",
                (tid, namespace, external, native),
            ).fetchone()
            if season is None:
                if native not in inferred:
                    continue
                season = (inferred[native],)
            hint = None
            for key in source_keys(name, state.provider):
                hint = state.db.execute(
                    "SELECT episode FROM canonical_hint WHERE title_id=? AND season=? AND title_key=?",
                    (tid, season[0], key),
                ).fetchone()
                if hint is not None:
                    break
            if hint is None or hint[0] is None:
                continue
            previous = state.db.execute(
                "SELECT season,episode FROM canonical_episode WHERE mapping_id=? AND entity_id=?",
                (mid, eid),
            ).fetchone()
            occupied = state.db.execute(
                "SELECT entity_id FROM canonical_episode WHERE mapping_id=? AND season=? AND episode=?",
                (mid, season[0], hint[0]),
            ).fetchone()
            if (
                previous
                and tuple(previous) != (season[0], hint[0])
                or occupied
                and occupied[0] != eid
            ):
                outcome = "conflict"
                continue
            state.db.execute(
                "INSERT INTO canonical_episode VALUES(?,?,?,?,NULL,'exact_title',?) ON CONFLICT(mapping_id,season,episode) DO UPDATE SET checked_at=excluded.checked_at",
                (mid, eid, season[0], hint[0], checked_at),
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
