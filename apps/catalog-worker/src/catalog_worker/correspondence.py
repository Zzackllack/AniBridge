"""One decision path for matching and bounded, metadata-free rejection reports."""

from collections import Counter, defaultdict
from dataclasses import dataclass

from .episode_matching import contextual_key, infer_seasons, source_keys
from .parent_evidence import status as parent_status
from .state import State

REASONS = frozenset(
    {
        "accepted",
        "already_mapped",
        "waiting_parent",
        "parent_conflict",
        "waiting_descriptor",
        "missing_name",
        "generic_name",
        "no_name_candidate",
        "duplicate_source",
        "duplicate_canonical",
        "alias_conflict",
        "coordinate_conflict",
        "source_failure",
        "parent_unresolved",
        "descriptor_empty",
        "unproved_season_context",
        "waiting_parent_verification",
    }
)


@dataclass(frozen=True)
class Decision:
    entity_id: str
    mapping_id: str | None
    reason: str
    coordinate: tuple[int, int] | None = None


def decisions(state: State, tid: str, *, contextual: bool = False) -> list[Decision]:
    """Read a bounded title, without changes or network access.

    A cache is evidence, not proof that its parent association is correct. Conflicts
    stay explicit; diagnostics never promote a guessed association or a number.
    """
    db = state.db
    parents = db.execute(
        "SELECT mapping_id,external_id,evidence FROM canonical_title WHERE title_id=? AND namespace='tvdb'",
        (tid,),
    ).fetchall()
    entities = db.execute(
        "SELECT entity_id,native_season,display_title FROM entity WHERE title_id=? AND kind='episode' ORDER BY entity_id",
        (tid,),
    ).fetchall()
    if len(entities) > 100000:
        raise ValueError("correspondence title limit")
    aliases = defaultdict(list)
    for eid, name in db.execute(
        "SELECT a.entity_id,a.display_title FROM entity_alias a JOIN entity e USING(entity_id) WHERE e.title_id=?",
        (tid,),
    ):
        aliases[eid].append(name)
    keys = {
        eid: {
            key
            for name in ([name] if name else []) + aliases[eid]
            for key in source_keys(name, state.provider)
            if key
        }
        for eid, _, name in entities
    }
    counts = Counter(key for values in keys.values() for key in values)
    seasonal_counts = Counter(
        (native, key) for eid, native, _ in entities for key in keys[eid]
    )
    hints = defaultdict(list)
    for season, key, episode in db.execute(
        "SELECT season,title_key,episode FROM canonical_hint WHERE title_id=?",
        (tid,),
    ):
        hints[key].append((season, episode))
    contextual_hints = defaultdict(set)
    for key, values in hints.items():
        contextual_hints[contextual_key(key)].update(values)
    contextual_counts = Counter(
        (native, contextual_key(key))
        for eid, native, _ in entities
        for key in {contextual_key(k) for k in keys[eid]}
    )
    inferred = infer_seasons(state, tid) if parents else {}
    reviewed = {
        native: season
        for native, season in db.execute(
            "SELECT native_season,canonical_season FROM season_correspondence WHERE title_id=? AND namespace='tvdb' AND external_id=?",
            (tid, parents[0][1] if len(parents) == 1 else ""),
        )
    }
    existing, occupied = {}, {}
    if len(parents) == 1:
        for eid, season, episode in db.execute(
            "SELECT entity_id,season,episode FROM canonical_episode WHERE mapping_id=?",
            (parents[0][0],),
        ):
            existing[eid] = (season, episode)
            occupied[(season, episode)] = eid
    result = []
    parent_proof = (
        parent_status(state, tid, parents[0][1], parents[0][2])
        if len(parents) == 1
        else None
    )
    for eid, native, name in entities:
        mid = parents[0][0] if len(parents) == 1 else None
        if len(parents) != 1:
            attempted = db.execute(
                "SELECT checked_at,outcome FROM mapping_input WHERE title_id=?", (tid,)
            ).fetchone()
            reason = (
                "parent_conflict"
                if parents
                else "source_failure"
                if attempted and attempted[1] == "source_failure"
                else "parent_unresolved"
                if attempted and attempted[0] is not None
                else "waiting_parent"
            )
        elif parent_proof != "verified":
            reason = parent_proof
        elif not db.execute(
            "SELECT 1 FROM canonical_cache WHERE title_id=?", (tid,)
        ).fetchone():
            reason = "waiting_descriptor"
        elif not name and not aliases[eid]:
            reason = "missing_name"
        elif not keys[eid]:
            reason = "generic_name"
        else:
            proven = reviewed.get(native, inferred.get(native))
            candidates, problems = set(), set()
            for key in keys[eid]:
                matches = [
                    hint for hint in hints[key] if proven is None or hint[0] == proven
                ]
                if not matches:
                    continue
                count = (
                    seasonal_counts[(native, key)]
                    if contextual and proven is not None
                    else counts[key]
                )
                if count != 1:
                    problems.add("duplicate_source")
                elif len(matches) != 1 or matches[0][1] is None:
                    problems.add(
                        "unproved_season_context"
                        if proven is None
                        and len(matches) > 1
                        and all(hint[1] is not None for hint in matches)
                        else "duplicate_canonical"
                    )
                else:
                    candidates.add(matches[0])
            if problems:
                reason = min(problems)
            elif len(candidates) > 1:
                reason = "alias_conflict"
            elif not candidates:
                # Three exact name anchors or an explicit reviewed season are
                # independent of this wording candidate. Never expand ambiguous
                # contractions, bridge sequence gaps, or use ordinal equality.
                if contextual and proven is not None:
                    for key in {contextual_key(key) for key in keys[eid]}:
                        matches = [
                            hint for hint in contextual_hints[key] if hint[0] == proven
                        ]
                        if (
                            len(matches) == 1
                            and matches[0][1] is not None
                            and contextual_counts[(native, key)] == 1
                        ):
                            candidates.add(matches[0])
                        elif matches:
                            problems.add("duplicate_canonical")
                if not candidates or problems:
                    reason = (
                        "no_name_candidate"
                        if not problems and hints
                        else "duplicate_canonical"
                        if problems
                        else "descriptor_empty"
                    )
                elif len(candidates) != 1:
                    reason = "alias_conflict"
                else:
                    coordinate = next(iter(candidates))
                    if (
                        eid in existing
                        and existing[eid] != coordinate
                        or coordinate in occupied
                        and occupied[coordinate] != eid
                    ):
                        reason = "coordinate_conflict"
                    else:
                        result.append(
                            Decision(
                                eid,
                                mid,
                                "already_mapped" if eid in existing else "accepted",
                                coordinate,
                            )
                        )
                        occupied[coordinate] = eid
                        continue
            else:
                coordinate = next(iter(candidates))
                if (
                    eid in existing
                    and existing[eid] != coordinate
                    or coordinate in occupied
                    and occupied[coordinate] != eid
                ):
                    reason = "coordinate_conflict"
                else:
                    result.append(
                        Decision(
                            eid,
                            mid,
                            "already_mapped" if eid in existing else "accepted",
                            coordinate,
                        )
                    )
                    # Also fence simultaneous candidates for one coordinate.
                    occupied[coordinate] = eid
                    continue
        if eid in existing and reason != "coordinate_conflict":
            result.append(Decision(eid, mid, "already_mapped", existing[eid]))
        else:
            result.append(Decision(eid, mid, reason))
    return result


def summary(state: State, tid: str, *, contextual: bool = False) -> dict[str, int]:
    """Only allowlisted aggregate codes leave the matcher boundary."""
    return dict(
        sorted(
            Counter(
                d.reason for d in decisions(state, tid, contextual=contextual)
            ).items()
        )
    )
