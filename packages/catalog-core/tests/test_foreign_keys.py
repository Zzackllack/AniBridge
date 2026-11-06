"""Ordered admission scans cover the exact DDL and agree with SQLite's oracle."""

import sqlite3

import pytest
from catalog_core import fixtures, schema
from catalog_core.compact import FOREIGN_KEYS, validate_foreign_keys


def test_all_fixed_schema_relationships_are_covered():
    with sqlite3.connect(":memory:") as db:
        db.executescript(schema.DDL_V2)
        expected = set()
        for (table,) in db.execute("SELECT name FROM sqlite_schema WHERE type='table'"):
            for _, _, parent, child_key, parent_key, *_ in db.execute(
                f"PRAGMA foreign_key_list({table})"
            ):
                assert child_key == parent_key
                expected.add((table, parent, child_key))
        assert expected == {record[:3] for record in FOREIGN_KEYS}


@pytest.mark.parametrize("child,parent,key,index", FOREIGN_KEYS)
def test_missing_parent_rejects_even_when_writer_disabled_constraints(
    tmp_path, child, parent, key, index
):
    _, payload, _, _ = fixtures.build(tmp_path, schema_version=2)
    filename = tmp_path / "fixture.sqlite"
    with sqlite3.connect(filename) as db:
        if child == "alias_data":
            db.execute(
                "INSERT INTO alias_data SELECT title_key,'alternate','Alternate' FROM title_data"
            )
            payload["counts"]["alias"] = 1
        assert not db.execute("PRAGMA foreign_key_check").fetchone()
        validate_foreign_keys(db)
        db.execute(f"UPDATE {child} SET {key}=99999999")
        assert db.execute("PRAGMA foreign_key_check").fetchone()
        with pytest.raises(ValueError, match="invalid foreign keys"):
            validate_foreign_keys(db)
    with pytest.raises(ValueError, match="invalid foreign keys"):
        schema.validate(filename, payload)
