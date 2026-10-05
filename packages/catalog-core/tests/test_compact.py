"""Explicit schema compatibility, hidden-row attacks and unchanged identities."""

import sqlite3

import pytest
from catalog_core import fixtures, manifest, schema
from catalog_core.compact import Writer
from catalog_core.json_codec import ContractError


@pytest.mark.parametrize("provider", ["aniworld.to", "s.to", "megakino"])
@pytest.mark.parametrize("movie", [False, True])
def test_records_are_equal_between_layouts(tmp_path, provider, movie):
    records = []
    for version in (1, 2):
        root = tmp_path / str(version)
        _, payload, envelope, key = fixtures.build(
            root, provider, movie=movie, schema_version=version
        )
        manifest.verify(envelope, [key], "synthetic", provider, payload["published_at"])
        with sqlite3.connect(root / "fixture.sqlite") as db:
            tid = db.execute("SELECT title_id FROM title").fetchone()[0]
            Writer(db, version).insert("alias", (tid, "alternate", "Alternate"))
            Writer(db, version).insert("identity_alias", ("title", "0" * 64, tid))
            payload["counts"]["alias"] = payload["counts"]["identity_alias"] = 1
            records.append(
                {
                    table: db.execute(f"SELECT * FROM {table} ORDER BY 1,2").fetchall()
                    for table in manifest.TABLE_LIMITS
                }
            )
        assert schema.validate(root / "fixture.sqlite", payload) == payload["counts"]
    assert records[0] == records[1]


@pytest.mark.parametrize("claimed", [1, 3])
def test_layout_is_not_silently_interpreted_as_another_version(tmp_path, claimed):
    _, payload, _, _ = fixtures.build(tmp_path, schema_version=2)
    payload["catalog_schema_version"] = claimed
    with pytest.raises(ContractError):
        schema.validate(tmp_path / "fixture.sqlite", payload)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE title_data SET title_key=-1",
        "UPDATE title_data SET path=identity_anchor",
        "UPDATE entity_data SET path=identity_anchor",
        "UPDATE entity_data SET title_key=999",
        "UPDATE release_data SET entity_key=999",
        "UPDATE release_data SET entity_key=0",
        "UPDATE canonical_episode_data SET mapping_key=999",
        "UPDATE canonical_episode_data SET entity_key=999",
        "UPDATE title_data SET media_type='invalid'",
        "UPDATE entity_data SET native_episode=0",
        "UPDATE release_data SET first_seen_at=-1",
        "UPDATE canonical_title_data SET evidence='guessed'",
        "UPDATE canonical_episode_data SET evidence='ordinal'",
        "DROP VIEW release",
        "DROP VIEW alias; CREATE VIEW alias AS SELECT NULL AS title_id,search_key,display_alias FROM alias_data",
        "CREATE TABLE private_cookie(value TEXT)",
        "CREATE INDEX extra_index ON release_data(observed_at)",
    ],
)
def test_hostile_compact_rows_and_definitions_reject(tmp_path, statement):
    _, payload, _, _ = fixtures.build(tmp_path, schema_version=2)
    path = tmp_path / "fixture.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA ignore_check_constraints=ON")
        db.executescript(statement)
    with pytest.raises(ContractError):
        schema.validate(path, payload)


def test_renamed_paths_keep_the_original_identity(tmp_path):
    _, payload, _, _ = fixtures.build(tmp_path, schema_version=2)
    with sqlite3.connect(tmp_path / "fixture.sqlite") as db:
        before = db.execute("SELECT title_id,identity_anchor FROM title").fetchone()
        db.execute("UPDATE title_data SET path='/anime/stream/renamed'")
        assert (
            db.execute("SELECT title_id,identity_anchor FROM title").fetchone()
            == before
        )
        assert (
            db.execute("SELECT path FROM title").fetchone()[0]
            == "/anime/stream/renamed"
        )
    assert schema.validate(tmp_path / "fixture.sqlite", payload) == payload["counts"]
