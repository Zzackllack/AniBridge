"""Mutate exported bytes, keeping row counts current to reach semantic checks."""

import sqlite3

import pytest

from catalog_core import fixtures, manifest, schema
from catalog_core.json_codec import ContractError

TABLES = ("catalog", *manifest.TABLE_LIMITS)
INDEXES = (
    "title_search",
    "title_slug",
    "alias_search",
    "entity_title",
    "release_recent",
    "canonical_lookup",
    "canonical_episode_entity",
)


def candidate(tmp_path, statements):
    _, payload, _, _ = fixtures.build(tmp_path)
    path = tmp_path / "fixture.sqlite"
    with sqlite3.connect(path) as db:
        # Hostile SQLite files can contain rows inserted with enforcement off.
        # The consumer must recheck these rather than trusting writer settings.
        db.execute("PRAGMA ignore_check_constraints=ON")
        for statement in statements:
            db.execute(statement)
        payload["counts"] = {
            table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in manifest.TABLE_LIMITS
        }
    return path, payload


@pytest.mark.parametrize("table", TABLES)
def test_missing_fixed_table_is_rejected(tmp_path, table):
    _, payload, _, _ = fixtures.build(tmp_path)
    path = tmp_path / "fixture.sqlite"
    with sqlite3.connect(path) as db:
        db.execute(f"DROP TABLE {table}")
    with pytest.raises(ContractError, match="schema"):
        schema.validate(path, payload)


@pytest.mark.parametrize("index", INDEXES)
@pytest.mark.parametrize("replace", [False, True])
def test_missing_or_changed_index_is_rejected(tmp_path, index, replace):
    _, payload, _, _ = fixtures.build(tmp_path)
    path = tmp_path / "fixture.sqlite"
    with sqlite3.connect(path) as db:
        db.execute(f"DROP INDEX {index}")
        if replace:
            db.execute(f"CREATE INDEX {index} ON title(observed_at)")
    with pytest.raises(ContractError, match="schema"):
        schema.validate(path, payload)


@pytest.mark.parametrize(
    "pragma",
    [
        "application_id=0",
        "user_version=0",
        "page_size=8192",
        "journal_mode=WAL",
    ],
)
def test_wrong_sqlite_header_is_rejected(tmp_path, pragma):
    _, payload, _, _ = fixtures.build(tmp_path)
    path = tmp_path / "fixture.sqlite"
    with sqlite3.connect(path) as db:
        db.execute(f"PRAGMA {pragma}")
        if pragma.startswith("page_size"):
            db.execute("VACUUM")
    with pytest.raises(ContractError, match="header"):
        schema.validate(path, payload)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE catalog SET provider='s.to'",
        "UPDATE catalog SET listing_checked_at=listing_checked_at-1",
        "UPDATE title SET media_type='invalid'",
        "UPDATE title SET year=1799",
        "UPDATE title SET observed_at=-1",
        "UPDATE title SET observed_at=1800000301",
        "UPDATE title SET detail_status='invalid'",
        "UPDATE title SET title_id='not-a-digest'",
        "UPDATE title SET path='/anime/stream/example/'",
        "UPDATE title SET identity_anchor='/other'",
        "UPDATE entity SET kind='invalid'",
        "UPDATE entity SET native_season=-1",
        "UPDATE entity SET native_episode=0",
        "UPDATE entity SET native_episode=NULL",
        "UPDATE entity SET observed_at=-1",
        "UPDATE entity SET kind='movie',native_season=NULL,native_episode=NULL",
        "UPDATE entity SET entity_id='" + "0" * 64 + "'",
        "UPDATE release SET language='unknown' WHERE language='de-dub'",
        "UPDATE release SET first_seen_at=-1",
        "UPDATE release SET observed_at=first_seen_at-1",
        "UPDATE release SET release_id='" + "0" * 64 + "' WHERE language='de-dub'",
        "UPDATE canonical_title SET namespace='invalid'",
        "UPDATE canonical_title SET external_id='01'",
        "UPDATE canonical_title SET external_id='0'",
        "UPDATE canonical_title SET source='https://source.invalid'",
        "UPDATE canonical_title SET evidence='guess'",
        "UPDATE canonical_title SET checked_at=-1",
        "UPDATE canonical_title SET mapping_id='" + "0" * 64 + "'",
        "UPDATE canonical_episode SET season=-1",
        "UPDATE canonical_episode SET episode=0",
        "UPDATE canonical_episode SET evidence='ordinal'",
        "UPDATE canonical_episode SET checked_at=-1",
        "INSERT INTO alias SELECT title_id,'wrong','Example alias' FROM title",
        "INSERT INTO alias VALUES ('" + "0" * 64 + "','missing','Missing')",
        "INSERT INTO identity_alias SELECT 'title','"
        + "0" * 64
        + "',entity_id FROM entity",
        "INSERT INTO identity_alias SELECT 'entity','"
        + "0" * 64
        + "',title_id FROM title",
    ],
)
def test_invalid_rows_are_rejected(tmp_path, statement):
    path, payload = candidate(tmp_path, [statement])
    with pytest.raises(ContractError):
        schema.validate(path, payload)


@pytest.mark.parametrize(
    "column,limit",
    [
        ("display_title", 512),
        ("search_key", 512),
        ("slug", 256),
        ("path", 1024),
        ("identity_anchor", 1024),
    ],
)
def test_utf8_string_limits_are_enforced(tmp_path, column, limit):
    _, payload, _, _ = fixtures.build(tmp_path)
    path = tmp_path / "fixture.sqlite"
    with sqlite3.connect(path) as db:
        db.execute(f"UPDATE title SET {column}=?", ("é" * (limit // 2 + 1),))
    with pytest.raises(ContractError, match="string too large"):
        schema.validate(path, payload)


def test_identity_alias_chain_is_rejected(tmp_path):
    first, second = "0" * 64, "1" * 64
    path, payload = candidate(
        tmp_path,
        [
            f"INSERT INTO identity_alias VALUES ('title','{first}','{second}')",
            f"INSERT INTO identity_alias SELECT 'title','{second}',title_id FROM title",
        ],
    )
    with pytest.raises(ContractError, match="semantic association"):
        schema.validate(path, payload)


@pytest.mark.parametrize("table", manifest.TABLE_LIMITS)
def test_signed_count_disagreement_is_rejected(tmp_path, table):
    _, payload, _, _ = fixtures.build(tmp_path)
    payload["counts"][table] += 1
    with pytest.raises(ContractError, match="count"):
        schema.validate(tmp_path / "fixture.sqlite", payload)


@pytest.mark.parametrize("table,maximum", manifest.TABLE_LIMITS.items())
def test_signed_count_above_safety_ceiling_is_rejected(tmp_path, table, maximum):
    _, payload, _, _ = fixtures.build(tmp_path)
    payload["counts"][table] = maximum + 1
    with pytest.raises(ContractError, match="integer"):
        manifest.validate_payload(payload)
