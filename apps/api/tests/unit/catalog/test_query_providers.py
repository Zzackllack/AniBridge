"""All-provider production discovery, long titles and correction supersets."""

import asyncio
import json
import sqlite3
from contextlib import closing

import pytest
from app.catalog.query_providers import ProviderSearch
from catalog_core import artifact, fixtures, identity, schema
from catalog_core.compact import Writer
from test_query_local import NOW, insert_override, setup


@pytest.mark.parametrize("schema_version", [1, 2])
def test_long_series_target_and_correction_before_pagination(tmp_path, schema_version):
    client, search, database, root = setup(tmp_path)
    with closing(sqlite3.connect(root / "fixture.sqlite")) as db, db:
        tid = db.execute("SELECT title_id FROM title").fetchone()[0]
        mid = db.execute("SELECT mapping_id FROM canonical_title").fetchone()[0]
        for n in range(1, 601):
            path = f"/anime/stream/example/staffel-2/episode-{n}"
            eid = identity.entity_id("aniworld.to", path)
            db.execute(
                "INSERT INTO entity VALUES(?,?,?,?,?,?,?,?,?)",
                (eid, tid, path, "episode", 2, n, f"Distinct {n}", path, NOW),
            )
            db.execute(
                "INSERT INTO canonical_episode VALUES(?,?,?,?,?,?,?)",
                (
                    mid,
                    eid,
                    (n - 1) // 100 + 1,
                    (n - 1) % 100 + 1,
                    None,
                    "reviewed",
                    NOW,
                ),
            )
            for language in identity.LANGUAGES:
                db.execute(
                    "INSERT INTO release VALUES(?,?,?,?,?)",
                    (
                        identity.release_id("aniworld.to", eid, language),
                        eid,
                        language,
                        NOW,
                        NOW,
                    ),
                )
    metadata = json.loads((root / "current.json").read_text())
    metadata["artifact"]["sqlite_sha256"] = artifact.sha256(root / "fixture.sqlite")
    (root / "current.json").write_text(json.dumps(metadata))
    insert_override(database, root, "episode", ("123", 5, 101))
    if schema_version == 2:
        compact = root / "compact.sqlite"
        with (
            closing(schema.connect(root / "fixture.sqlite")) as source,
            closing(schema.create(compact, version=2)) as target,
            target,
        ):
            writer = Writer(target, 2)
            for table in (
                "catalog",
                "title",
                "alias",
                "entity",
                "release",
                "canonical_title",
                "canonical_episode",
                "identity_alias",
            ):
                for row in source.execute(f"SELECT * FROM {table}"):
                    values = list(row)
                    if table == "catalog":
                        values[2] = 2
                    writer.insert(table, tuple(values))
        metadata.update(database="compact.sqlite", catalog_schema_version=2)
        metadata["artifact"]["sqlite_sha256"] = artifact.sha256(compact)
        (root / "current.json").write_text(json.dumps(metadata))

    async def run():
        rows, total, _ = await search.search(
            {"t": "tvsearch", "tvdbid": "123", "season": "5", "ep": "101"}, now=NOW
        )
        assert total == 4 and len(rows) == 4
        assert client.requests == 2
        assert all((r["native_season"], r["native_episode"]) == (1, 2) for r in rows)
        rows, total, _ = await search.search(
            {"t": "tvsearch", "tvdbid": "123", "season": "5", "offset": "100"},
            now=NOW,
            languages={"aniworld.to": {"de-dub", "en-sub"}},
        )
        assert total == 202 and len(rows) == 100
        _, old_total, _ = await search.search(
            {"t": "tvsearch", "tvdbid": "123", "season": "0"}, now=NOW
        )
        assert old_total == 0
        with pytest.raises(ValueError, match="query_too_broad"):
            await search.search({"t": "search", "q": "Example"}, now=NOW)
        await client.close()

    asyncio.run(run())


def test_provider_discovery_movie_identity_and_independent_outage(tmp_path):
    client, _, database, root = setup(tmp_path)
    for provider, movie in (("s.to", False), ("megakino", True)):
        _, metadata, _, _ = fixtures.build(
            root / provider,
            provider=provider,
            movie=movie,
            now=NOW,
            revision=7 if movie else 2,
        )
        metadata["database"] = "fixture.sqlite"
        (root / provider / "current.json").write_text(json.dumps(metadata))
    search = ProviderSearch(
        client, database, tmp_path, ("aniworld.to", "s.to", "megakino")
    )

    async def run():
        rows, total, _ = await search.search(
            {"t": "tvsearch", "tvdbid": "123", "season": "0"}, now=NOW
        )
        assert total == 8 and {r["provider"] for r in rows} == {"aniworld.to", "s.to"}
        rows, total, _ = await search.search({"t": "movie", "tmdbid": "123"}, now=NOW)
        assert total == 4 and all(
            r["kind"] == "movie" and r["season"] is None and r["native_episode"] is None
            for r in rows
        )
        assert client.revision_floor("s.to") == 2 and client.revision_floor() == 1
        client.cache.clear()
        (root / "s.to" / "current.json").unlink()
        rows, total, headers = await search.search(
            {"t": "tvsearch", "tvdbid": "123", "season": "0"}, now=NOW
        )
        assert total == 4 and all(r["provider"] == "aniworld.to" for r in rows)
        assert headers["X-AniBridge-Catalog-Unavailable"] == "s.to"
        await client.close()

    asyncio.run(run())


def test_empty_sibling_does_not_hide_provider_outage(tmp_path):
    from catalog_core.query_client import Unavailable

    client, _, database, root = setup(tmp_path)
    search = ProviderSearch(client, database, tmp_path, ("aniworld.to", "s.to"))

    async def run():
        with pytest.raises(Unavailable, match="catalog_unavailable"):
            await search.search({"t": "tvsearch", "q": "Absent ordinary show"}, now=NOW)
        await client.close()

    asyncio.run(run())
