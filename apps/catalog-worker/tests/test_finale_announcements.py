"""Provider announcements are not part of an episode's canonical name."""

import json
from collections import defaultdict
from pathlib import Path

import pytest
from catalog_core.identity import search_key
from test_matching_followup import NOW, episode, seed

from catalog_worker import canonical_cache
from catalog_worker.correspondence import decisions
from catalog_worker.episode_matching import source_keys
from catalog_worker.mapping import CanonicalEpisode

FIXTURE = json.loads(
    (
        Path(__file__).parent / "fixtures/finale-announcements-2026-10-19.json"
    ).read_text()
)


@pytest.mark.parametrize(
    "case", FIXTURE["cases"], ids=lambda case: case["entity_id"][:12]
)
def test_frozen_announcements_keep_unique_names_and_conflicting_aliases(tmp_path, case):
    state, tid = seed(tmp_path)
    try:
        eid = episode(
            state, tid, 9, 7, case["source_names"][0], tuple(case["source_names"][1:])
        )
        grouped = defaultdict(list)
        for row in case["canonical_names"]:
            grouped[row["season"], row["episode"]].append(row["title_key"])
        with state.db:
            canonical_cache.store(
                state,
                tid,
                "digest",
                "parent-matcher",
                NOW,
                [
                    CanonicalEpisode(s, e, names[0], aliases=tuple(names[1:]))
                    for (s, e), names in grouped.items()
                ],
            )
            before = canonical_cache.fingerprints(state, tid)
            # Simulate the previous matcher receipt with unchanged source/cache.
            state.db.execute(
                "INSERT INTO matching_replay VALUES(?,?,?,?,?,?)",
                (tid, *before, "unique-name-context-6", NOW, "{}"),
            )
            decision = next(
                d for d in decisions(state, tid, contextual=True) if d.entity_id == eid
            )
            assert decision.reason == case["expected"]
            assert decision.coordinate == (
                tuple(case["coordinate"]) if case["coordinate"] else None
            )
            assert (
                canonical_cache.apply(state, tid, NOW, examined_at=NOW + 1)
                != "unchanged"
            )
            mapped = state.db.execute(
                "SELECT season,episode FROM canonical_episode WHERE entity_id=?", (eid,)
            ).fetchone()
            assert (list(mapped) if mapped else None) == case["coordinate"]
            assert canonical_cache.fingerprints(state, tid) == before
            assert (
                state.db.execute(
                    "SELECT display_title FROM entity WHERE entity_id=?", (eid,)
                ).fetchone()[0]
                == case["source_names"][0]
            )
            assert (
                canonical_cache.apply(state, tid, NOW, examined_at=NOW + 2)
                == "unchanged"
            )
    finally:
        state.close()


@pytest.mark.parametrize(
    "name",
    [
        "A story [Final Episode | Director's Cut]",
        "A story [Season 5 confirmed - Start: tba]",
        "A story [Final Episode | Season 5 confirmed - Start: tba] Part II",
        "A story [Final Episode | Season 5 confirmed - Start: tba]]",
        "A story [Final Episode | Season 5 confirmed - Start: tomorrow]",
    ],
)
def test_unverified_or_meaningful_bracket_text_is_retained(name):
    assert source_keys(name, "aniworld.to") == (search_key(name),)


def test_announcement_rules_are_provider_specific_and_never_supply_names():
    name = "Episode 16 [Final Episode | Season 5 confirmed - Start: tba]"
    assert source_keys(name, "aniworld.to") == ()
    assert source_keys(name, "s.to") == (search_key(name),)


def test_announcements_do_not_resolve_duplicate_source_names(tmp_path):
    state, tid = seed(tmp_path)
    try:
        name = "The ending [Final Episode | Season 5 confirmed - Start: tba]"
        episode(state, tid, 9, 7, name)
        episode(state, tid, 9, 8, name)
        with state.db:
            canonical_cache.store(
                state,
                tid,
                "digest",
                "parent-matcher",
                NOW,
                [CanonicalEpisode(2, 11, "The ending")],
            )
        assert {d.reason for d in decisions(state, tid, contextual=True)} == {
            "duplicate_source"
        }
    finally:
        state.close()
