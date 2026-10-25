"""Publication deltas, admission trust, concurrent collection and v6 recovery."""

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from catalog_core import schema
from catalog_worker import read_catalog
from catalog_worker.publication_state import pending
from catalog_worker.state import State
from test_query import NOW, seed


def rows(config, metadata):
    with schema.connect(config.output_dir / metadata["database"]) as db:
        return {
            table: {tuple(r) for r in db.execute(f"SELECT * FROM {table}")}
            for table in metadata["counts"]
        }


def test_content_and_observation_changes_have_separate_durable_cadences(tmp_path):
    state, config = seed(tmp_path)
    config = replace(config, limits={**config.limits, "publish_interval_s": 300})
    initial = dict(state.db.execute("SELECT * FROM publication_meta").fetchone())
    with state.db:
        state.db.execute("UPDATE entity SET observed_at=?", (NOW + 1,))
    fresh = dict(state.db.execute("SELECT * FROM publication_meta").fetchone())
    assert fresh["generation"] > initial["generation"]
    assert fresh["content_generation"] == initial["content_generation"]
    assert not pending(config, state, NOW + 300)
    assert pending(config, state, NOW + 3600)
    with state.db:
        state.db.execute("UPDATE entity SET display_title='New verified name'")
    assert pending(config, state, NOW + 300)
    filename = Path(state.db.execute("PRAGMA database_list").fetchone()[2])
    state.close()
    state = State(filename, "aniworld.to")
    assert pending(config, state, NOW + 300)
    # No-op SQL and scheduling/lease changes must not advance the generation.
    before = dict(state.db.execute("SELECT * FROM publication_meta").fetchone())
    with state.db:
        state.db.execute("UPDATE entity SET display_title=display_title")
        state.db.execute("UPDATE work SET lease_until=?", (NOW + 200,))
    assert dict(state.db.execute("SELECT * FROM publication_meta").fetchone()) == before
    state.close()


@pytest.mark.parametrize(
    "change",
    [
        "UPDATE entity SET display_title='Changed'",
        "UPDATE release SET observed_at=observed_at+1",
        "UPDATE canonical_episode SET season=2,episode=7",
        "UPDATE canonical_title SET source='unapproved'",
        "INSERT INTO omissions VALUES('release',(SELECT release_id FROM release LIMIT 1),1800000000,3,1,1)",
        "INSERT INTO omissions VALUES('entity',(SELECT entity_id FROM entity LIMIT 1),1800000000,3,1,1)",
        "INSERT INTO omissions VALUES('title',(SELECT title_id FROM title LIMIT 1),1800000000,3,1,1)",
        "INSERT INTO alias SELECT title_id,'extra','Extra' FROM title",
        "DELETE FROM canonical_episode",
        "INSERT INTO identity_alias SELECT 'entity',printf('%064d',0),entity_id FROM entity",
    ],
)
def test_incremental_projection_equals_independent_full_export(tmp_path, change):
    state, config = seed(tmp_path)
    try:
        with state.db:
            state.db.execute(change)
        incremental = read_catalog.publish(config, state, NOW + 2)
        actual = rows(config, incremental)
        full = read_catalog.publish(
            replace(config, output_dir=tmp_path / "independent"),
            state,
            NOW + 2,
            full=True,
        )
        assert (
            rows(replace(config, output_dir=tmp_path / "independent"), full) == actual
        )
        assert full["counts"] == incremental["counts"]
        assert full["release_summary"] == incremental["release_summary"]
    finally:
        state.close()


def test_collection_commit_during_export_stays_pending_and_snapshot_is_consistent(
    tmp_path, monkeypatch
):
    state, config = seed(tmp_path)
    config = replace(config, limits={**config.limits, "publish_interval_s": 300})
    original = read_catalog.copy
    original_name = state.db.execute("SELECT display_title FROM entity").fetchone()[0]
    filename = Path(state.db.execute("PRAGMA database_list").fetchone()[2])

    def copy_with_collection(db, *args, **kwargs):
        # The progress callback runs while the attached ledger snapshot is open.
        wrote = False

        def concurrent_write():
            nonlocal wrote
            if not wrote and db.in_transaction:
                wrote = True
                with sqlite3.connect(filename, timeout=0.1) as writer:
                    writer.execute(
                        "UPDATE entity SET display_title='Arrived during export'"
                    )
            return False

        db.set_progress_handler(concurrent_write, 100)
        result = original(db, *args, **kwargs)
        assert wrote
        return result

    monkeypatch.setattr(read_catalog, "copy", copy_with_collection)
    first = read_catalog.publish(config, state, NOW + 300)
    with schema.connect(config.output_dir / first["database"]) as db:
        assert (
            db.execute("SELECT display_title FROM entity").fetchone()[0]
            == original_name
        )
    assert pending(config, state, NOW + 600) and state.meta()["dirty"] == 1
    monkeypatch.setattr(read_catalog, "copy", original)
    second = read_catalog.publish(config, state, NOW + 600)
    with schema.connect(config.output_dir / second["database"]) as db:
        assert (
            db.execute("SELECT display_title FROM entity").fetchone()[0]
            == "Arrived during export"
        )
    assert not pending(config, state, NOW + 900)
    state.close()


def test_mutations_outside_planned_partition_are_still_row_validated(
    tmp_path, monkeypatch
):
    state, config = seed(tmp_path)
    pointer = (config.output_dir / "current.json").read_bytes()
    original = read_catalog.copy

    def mutate(db, *args, **kwargs):
        result = original(db, *args, **kwargs)
        with db:
            db.execute("UPDATE title_data SET search_key='wrong normalization'")
        return result

    monkeypatch.setattr(read_catalog, "copy", mutate)
    with pytest.raises(ValueError, match="normalization"):
        read_catalog.publish(config, state, NOW + 1)
    assert (config.output_dir / "current.json").read_bytes() == pointer
    assert not (config.output_dir / "staging.sqlite").exists()
    state.close()


def test_base_tampering_and_policy_change_require_full_admission(tmp_path, monkeypatch):
    state, config = seed(tmp_path)
    pointer = json.loads((config.output_dir / "current.json").read_text())
    with sqlite3.connect(config.output_dir / pointer["database"]) as altered:
        altered.execute("UPDATE title_data SET search_key='tampered'")
    seen = []
    original = read_catalog.copy

    def observe(*args, **kwargs):
        seen.append(kwargs["incremental"])
        return original(*args, **kwargs)

    monkeypatch.setattr(read_catalog, "copy", observe)
    read_catalog.publish(config, state, NOW + 1)
    assert seen == [False]
    policy = replace(config, publication_sources=frozenset())
    assert pending(policy, state, NOW + config.limits["publish_interval_s"] + 1)
    read_catalog.publish(policy, state, NOW + 2)
    assert seen == [False, False]
    state.close()


@pytest.mark.parametrize(
    "change", ["rename_title", "new_episode", "late_map", "delete", "reparent"]
)
def test_added_deleted_and_reparented_rows_use_incremental_path(
    tmp_path, monkeypatch, change
):
    from catalog_core import identity

    state, config = seed(tmp_path)
    title_path = "/anime/stream/another-example"
    title_id = identity.title_id("aniworld.to", title_path)
    entity_path = title_path + "/staffel-1/episode-1"
    entity_id = identity.entity_id("aniworld.to", entity_path)
    with state.db:
        state.db.execute(
            "INSERT INTO title SELECT ?,?,?,?,?,media_type,year,?,observed_at,detail_status FROM title",
            (
                title_id,
                title_path,
                "another-example",
                "Another Example",
                "another example",
                title_path,
            ),
        )
    # New title discovery must also work without falling back to a full export.
    original_copy = read_catalog.copy

    def incremental_only(*args, **kwargs):
        assert kwargs["incremental"]
        return original_copy(*args, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(read_catalog, "copy", incremental_only)
        read_catalog.publish(config, state, NOW + 1)
    with state.db:
        if change == "rename_title":
            state.db.execute(
                "UPDATE title SET display_title='New name',search_key='new name' WHERE title_id=?",
                (title_id,),
            )
        elif change == "new_episode":
            state.db.execute(
                "INSERT INTO entity VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    entity_id,
                    title_id,
                    entity_path,
                    "episode",
                    1,
                    1,
                    "First",
                    entity_path,
                    NOW,
                ),
            )
            state.db.execute(
                "INSERT INTO release VALUES(?,?,?,?,?)",
                (
                    identity.release_id("aniworld.to", entity_id, "de-dub"),
                    entity_id,
                    "de-dub",
                    NOW,
                    NOW,
                ),
            )
        elif change == "late_map":
            original_tid, original_eid = state.db.execute(
                "SELECT title_id,entity_id FROM entity"
            ).fetchone()
            mapping = identity.mapping_id("aniworld.to", original_tid, "tmdb-tv", "456")
            state.db.execute(
                "INSERT INTO canonical_title VALUES(?,?,?,?,?,?,?)",
                (
                    mapping,
                    original_tid,
                    "tmdb-tv",
                    "456",
                    "synthetic-v1",
                    "reviewed",
                    NOW,
                ),
            )
            state.db.execute(
                "INSERT INTO canonical_episode VALUES(?,?,?,?,?,?,?)",
                (mapping, original_eid, 3, 5, None, "reviewed", NOW),
            )
        elif change == "delete":
            state.db.execute("DELETE FROM canonical_episode")
            state.db.execute("DELETE FROM canonical_title")
            state.db.execute("DELETE FROM release")
            state.db.execute("DELETE FROM entity")
            state.db.execute("DELETE FROM alias")
            state.db.execute("DELETE FROM observation_gap")
            for table in (
                "work",
                "title_schedule",
                "season_correspondence",
                "canonical_cache",
                "mapping_input",
                "matching_replay",
            ):
                # Physical deletion is exceptional; remove private fixture parents
                # as a repair command would, instead of disabling foreign keys.
                if state.db.execute(
                    "SELECT 1 FROM sqlite_schema WHERE name=?", (table,)
                ).fetchone():
                    state.db.execute(
                        f"DELETE FROM {table} WHERE title_id<>?", (title_id,)
                    )
            state.db.execute("DELETE FROM title WHERE title_id<>?", (title_id,))
        else:
            state.db.execute("UPDATE entity SET title_id=?", (title_id,))
            state.db.execute("DELETE FROM canonical_episode")
    seen = []
    original = read_catalog.copy

    def observe(*args, **kwargs):
        seen.append(kwargs["incremental"])
        return original(*args, **kwargs)

    monkeypatch.setattr(read_catalog, "copy", observe)
    current = read_catalog.publish(config, state, NOW + 2)
    assert seen == [True]
    actual = rows(config, current)
    other = replace(config, output_dir=tmp_path / "independent")
    full = read_catalog.publish(other, state, NOW + 2, full=True)
    assert rows(other, full) == actual
    state.close()


def test_journal_rolls_back_with_source_and_ack_crash_rebuilds_safely(
    tmp_path, monkeypatch
):
    state, config = seed(tmp_path)
    before = tuple(state.db.execute("SELECT * FROM publication_meta").fetchone())
    with pytest.raises(RuntimeError), state.db:
        state.db.execute("UPDATE entity SET display_title='Rolled back'")
        raise RuntimeError("controlled rollback")
    assert (
        tuple(state.db.execute("SELECT * FROM publication_meta").fetchone()) == before
    )
    with state.db:
        state.db.execute("UPDATE entity SET display_title='Committed'")
    original = read_catalog.acknowledge

    def crash(*args):
        raise RuntimeError("after pointer, before acknowledgement")

    monkeypatch.setattr(read_catalog, "acknowledge", crash)
    with pytest.raises(RuntimeError):
        read_catalog.publish(config, state, NOW + 1)
    read_catalog.verify(config.output_dir)
    assert state.db.execute("SELECT count(*) FROM publication_change").fetchone()[0] > 0
    monkeypatch.setattr(read_catalog, "acknowledge", original)
    result = read_catalog.publish(config, state, NOW + 2)
    assert result["revision"] == 3
    assert (
        state.db.execute("SELECT count(*) FROM publication_change").fetchone()[0] == 0
    )
    state.close()


def test_external_stage_writer_invalidates_reused_validation(tmp_path, monkeypatch):
    state, config = seed(tmp_path)
    pointer = (config.output_dir / "current.json").read_bytes()
    original = schema.validate

    def validate_with_writer(path, payload, *args, **kwargs):
        result = original(path, payload, *args, **kwargs)
        with sqlite3.connect(path) as writer:
            writer.execute("UPDATE entity_data SET display_title='External write'")
        return result

    monkeypatch.setattr(schema, "validate", validate_with_writer)
    with pytest.raises(ValueError, match="staging changed outside publisher"):
        read_catalog.publish(config, state, NOW + 1)
    assert (config.output_dir / "current.json").read_bytes() == pointer
    assert not (config.output_dir / "staging.sqlite").exists()
    state.close()


def test_backwards_publication_clock_cannot_reuse_future_row_proof(
    tmp_path, monkeypatch
):
    state, config = seed(tmp_path)
    seen = []
    original = read_catalog.copy

    def observe(*args, **kwargs):
        seen.append(kwargs["incremental"])
        return original(*args, **kwargs)

    monkeypatch.setattr(read_catalog, "copy", observe)
    with pytest.raises(ValueError, match="timestamp"):
        read_catalog.publish(config, state, NOW - 301)
    assert seen == [False]
    state.close()


@pytest.mark.parametrize("unclassified", [True, False])
def test_unclassified_or_broad_journal_falls_back_to_full(
    tmp_path, monkeypatch, unclassified
):
    state, config = seed(tmp_path)
    generation = state.db.execute("SELECT generation FROM publication_meta").fetchone()[
        0
    ]
    with state.db:
        state.db.executemany(
            "INSERT INTO publication_change VALUES(?,?)",
            [("@full", generation)]
            if unclassified
            else [(f"{i:064x}", generation) for i in range(1001)],
        )
    seen = []
    original = read_catalog.copy

    def observe(*args, **kwargs):
        seen.append(kwargs["incremental"])
        return original(*args, **kwargs)

    monkeypatch.setattr(read_catalog, "copy", observe)
    read_catalog.publish(config, state, NOW + 1)
    assert seen == [True, False]
    assert (
        state.db.execute("SELECT count(*) FROM publication_change").fetchone()[0] == 0
    )
    state.close()


def test_abandoned_staging_is_cleaned_before_quota_admission(tmp_path, monkeypatch):
    state, config = seed(tmp_path)
    before = rows(config, read_catalog.verify(config.output_dir))
    scratch = [
        config.output_dir / ("staging.sqlite" + suffix)
        for suffix in ("", "-journal", "-wal", "-shm")
    ]
    for path in scratch:
        path.write_bytes(b"owned interrupted publication scratch")
    original = read_catalog.check
    admitted = False

    def check_after_recovery(*args, **kwargs):
        nonlocal admitted
        if not admitted:
            assert not any(path.exists() for path in scratch)
            admitted = True
        return original(*args, **kwargs)

    monkeypatch.setattr(read_catalog, "check", check_after_recovery)
    result = read_catalog.publish(config, state, NOW + 1)
    assert admitted and rows(config, result) == before
    state.close()


def test_active_staging_owner_prevents_scratch_cleanup(tmp_path):
    from catalog_core.files import ProcessLock

    state, config = seed(tmp_path)
    scratch = config.output_dir / "staging.sqlite-journal"
    scratch.write_bytes(b"belongs to active publisher")
    owner = ProcessLock(config.output_dir / "publish.lock")
    try:
        with pytest.raises(RuntimeError, match="already owned"):
            read_catalog.publish(config, state, NOW + 1)
        assert scratch.read_bytes() == b"belongs to active publisher"
    finally:
        owner.close()
        state.close()
