"""Both observed TVDB episode layouts need explicit, consistent identity pairs."""

import asyncio
import json
from pathlib import Path

import pytest
from catalog_core.providers.transport import Fetch
from catalog_worker import descriptors
from catalog_worker.canonical import Enricher
from catalog_worker.canonical_failures import EvidenceError
from test_matching_followup import NOW, episode, seed

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/skyhook_legacy_episode_ids.json").read_text()
)


@pytest.mark.parametrize("series", FIXTURE["series"], ids=lambda s: s["title_id"][:8])
def test_frozen_heldout_legacy_pairs_keep_verified_ids_across_languages(series):
    primary = descriptors.episodes(series["payloads"]["eng"])
    translated = descriptors.episodes(series["payloads"]["deu"])
    assert primary[0].external_id == str(series["expected_first_episode_id"])
    assert translated[0].external_id == primary[0].external_id
    assert [(e.season, e.episode) for e in primary] == [(1, 1), (1, 2)]
    # A v2 generic-field response must describe exactly the same identities.
    generic = json.loads(json.dumps(series["payloads"]["eng"]))
    for row in generic["episodes"]:
        row["metadataId"] = row.pop("tvdbId")
        row["metadataShowId"] = row.pop("tvdbShowId")
    assert descriptors.episodes(generic) == primary


@pytest.mark.parametrize(
    "fields,reason",
    [
        ({}, "episode_identity_missing"),
        ({"tvdbId": 777}, "episode_identity_missing"),
        ({"tvdbId": 777, "metadataShowId": 123}, "episode_identity_missing"),
        ({"tvdbId": True, "tvdbShowId": 123}, "episode_identity_missing"),
        ({"tvdbId": 777, "tvdbShowId": 456}, "episode_parent_conflict"),
        (
            {
                "tvdbId": 777,
                "tvdbShowId": 123,
                "metadataId": 778,
                "metadataShowId": 123,
            },
            "episode_identity_conflict",
        ),
        (
            {
                "tvdbId": 777,
                "tvdbShowId": 123,
                "metadataId": None,
                "metadataShowId": None,
            },
            "episode_identity_missing",
        ),
        (
            {
                "tvdbId": 777,
                "tvdbShowId": 123,
                "metadataId": 777,
                "metadataShowId": 456,
            },
            "episode_parent_conflict",
        ),
    ],
)
def test_incomplete_or_contradictory_pairs_never_fall_back(fields, reason):
    payload = {
        "tvdbId": 123,
        "metadataSource": "tvdb",
        "episodes": [
            {"seasonNumber": 1, "episodeNumber": 1, "title": "A story", **fields}
        ],
    }
    with pytest.raises(EvidenceError) as failure:
        descriptors.episodes(payload)
    assert failure.value.reason == reason


def test_two_complete_pairs_must_agree():
    assert (
        descriptors.episode_identity(
            {
                "metadataId": 777,
                "metadataShowId": 123,
                "tvdbId": 777,
                "tvdbShowId": 123,
            },
            123,
        )
        == 777
    )


@pytest.mark.parametrize("translation_missing", [False, True])
def test_successful_retry_uses_names_retains_existing_maps_and_leaves_other_work(
    tmp_path,
    translation_missing,
):
    state, tid = seed(tmp_path)
    old = episode(state, tid, 9, 7, "A retained story")
    new = episode(state, tid, 9, 8, "A new verified story")
    generic = episode(state, tid, 9, 9, "Episode 9")
    with state.db:
        state.db.execute(
            "INSERT INTO canonical_episode VALUES(?,?,?,?,?,'exact_title',?)",
            (
                state.db.execute("SELECT mapping_id FROM canonical_title").fetchone()[
                    0
                ],
                old,
                2,
                3,
                None,
                NOW,
            ),
        )
        state.db.execute("UPDATE mapping_input SET failures=4,next_due=?", (NOW + 600,))
    work = [tuple(r) for r in state.db.execute("SELECT * FROM work")]
    releases = [tuple(r) for r in state.db.execute("SELECT * FROM release")]
    old_map = tuple(
        state.db.execute(
            "SELECT * FROM canonical_episode WHERE entity_id=?", (old,)
        ).fetchone()
    )
    calls = []

    async def fetch(origin, path, **kwargs):
        calls.append(path)
        item = {
            "tvdbId": 123,
            "title": "Example",
            "year": 2020,
            "metadataSource": "tvdb",
            "language": "deu" if "/deu/" in path else "eng",
            "episodes": [
                {
                    "tvdbId": 777,
                    "tvdbShowId": 123,
                    "title": "A retained story",
                    "seasonNumber": 2,
                    "episodeNumber": 3,
                },
                {
                    "tvdbId": 778,
                    "tvdbShowId": 123,
                    "title": "A new verified story",
                    "seasonNumber": 2,
                    "episodeNumber": 4,
                },
            ],
        }
        if translation_missing and "/deu/" in path:
            item.pop("language")
            for row in item["episodes"]:
                row["title"] = None
        return Fetch(
            "ok", json.dumps([item] if "search" in path else item).encode(), status=200
        )

    enricher = Enricher(
        {"episode_languages": ["deu"]}, fetcher=fetch, clock=lambda: NOW + 600
    )
    assert not asyncio.run(enricher.tick(state, NOW + 599))
    assert calls == []
    assert asyncio.run(enricher.tick(state, NOW + 600))
    assert enricher.last_failure is None
    assert state.db.execute("SELECT failures FROM mapping_input").fetchone()[0] == 0
    assert tuple(
        state.db.execute(
            "SELECT season,episode,external_episode_id FROM canonical_episode WHERE entity_id=?",
            (new,),
        ).fetchone()
    ) == (2, 4, "778")
    assert not state.db.execute(
        "SELECT 1 FROM canonical_episode WHERE entity_id=?", (generic,)
    ).fetchone()
    assert (
        tuple(
            state.db.execute(
                "SELECT * FROM canonical_episode WHERE entity_id=?", (old,)
            ).fetchone()
        )
        == old_map
    )
    assert [tuple(r) for r in state.db.execute("SELECT * FROM work")] == work
    assert [tuple(r) for r in state.db.execute("SELECT * FROM release")] == releases
    payload = json.loads(
        state.db.execute("SELECT payload FROM canonical_descriptor").fetchone()[0]
    )
    assert payload["missing_languages"] == (["deu"] if translation_missing else [])
    calls_before = len(calls)
    assert not asyncio.run(enricher.tick(state, NOW + 601))
    assert len(calls) == calls_before
    state.close()


@pytest.mark.parametrize("series", FIXTURE["series"], ids=lambda s: s["title_id"][:8])
def test_frozen_missing_translations_contribute_no_names(series):
    rows, missing = descriptors.translation(
        series["payloads"]["deu"], str(series["payloads"]["eng"]["tvdbId"]), "deu"
    )
    assert missing and rows == []


@pytest.mark.parametrize(
    "mutation",
    [
        {"language": "fra"},
        {"tvdbId": 456},
        {"metadataSource": "tmdb"},
        {
            "episodes": [
                {
                    "tvdbId": 777,
                    "tvdbShowId": 123,
                    "seasonNumber": 1,
                    "episodeNumber": 1,
                    "title": "Unknown language",
                }
            ]
        },
        {
            "episodes": [
                {
                    "tvdbId": 777,
                    "tvdbShowId": 123,
                    "seasonNumber": -1,
                    "episodeNumber": 1,
                    "title": "Unknown language",
                }
            ]
        },
    ],
)
def test_untagged_named_or_wrong_identity_translations_still_reject(mutation):
    payload = {"tvdbId": 123, "metadataSource": "tvdb", "episodes": [], **mutation}
    with pytest.raises(EvidenceError) as failure:
        descriptors.translation(payload, "123", "deu")
    assert failure.value.reason == "translation_identity_conflict"
