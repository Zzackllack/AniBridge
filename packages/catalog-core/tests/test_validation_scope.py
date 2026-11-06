"""Reusing row proofs never scopes out global artifact admission."""

import sqlite3

import pytest
from catalog_core import fixtures, schema
from catalog_core.json_codec import ContractError
from catalog_core.validation_scope import Scope, capture, captured


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE entity_data SET title_key=999",
        "DELETE FROM release_data",
        "CREATE INDEX unexpected ON release_data(observed_at)",
        "UPDATE catalog SET provider='s.to'",
    ],
)
def test_empty_row_scope_still_rejects_global_damage(tmp_path, statement):
    _, payload, _, _ = fixtures.build(tmp_path, schema_version=2)
    path = tmp_path / "fixture.sqlite"
    assert schema.validate(path, payload, scope=Scope(())) == payload["counts"]
    with sqlite3.connect(path) as db:
        db.execute(statement)
    with pytest.raises(ContractError):
        schema.validate(path, payload, scope=Scope(()))


def test_capture_includes_writes_and_preserves_untrusted_default(tmp_path):
    _, payload, _, _ = fixtures.build(tmp_path, schema_version=2)
    path = tmp_path / "fixture.sqlite"
    with sqlite3.connect(path) as db:
        capture(db)
        with db:
            db.execute("UPDATE title_data SET search_key='bad normalization'")
        scope = captured(db)
        assert scope.title_keys
        with pytest.raises(ContractError, match="normalization"):
            schema.validate(path, payload, scope=scope)
    with pytest.raises(ContractError, match="normalization"):
        schema.validate(path, payload)


@pytest.mark.parametrize("key", [-1, 0, True, "1 OR 1=1"])
def test_scope_rejects_nonpositive_or_noninteger_keys(key):
    with pytest.raises(ContractError, match="invalid validation scope"):
        Scope((key,)).query("title")


def test_expected_full_fallback_has_a_bounded_non_contract_reason():
    from catalog_core.diagnostics import reason

    assert reason(ValueError("full export required")) == "full_rebuild_required"
