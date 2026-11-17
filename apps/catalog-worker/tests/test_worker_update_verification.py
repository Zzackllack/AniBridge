"""Stopped-state checks protect release history and already accepted mappings."""

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "verify_worker_update",
    Path(__file__).resolve().parents[3]
    / "scripts/catalog/query_pilot/verify_worker_update.py",
)
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def ledger(path):
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE entity(id PRIMARY KEY);
            CREATE TABLE release(release_id PRIMARY KEY,first_seen_at);
            CREATE TABLE canonical_episode(id PRIMARY KEY,season,episode);
            CREATE TABLE work(id PRIMARY KEY,failures,due);
            CREATE TABLE canonical_scheduler(singleton PRIMARY KEY,slot);
            CREATE TABLE worker_meta(id PRIMARY KEY,bootstrap_finished,dirty,published_at);
            CREATE TABLE matching_replay(title_id PRIMARY KEY,source_hash,descriptor_hash,matcher);
            INSERT INTO entity VALUES('e');
            INSERT INTO release VALUES('r',123);
            INSERT INTO canonical_episode VALUES('e',2,5);
            INSERT INTO work VALUES('e',3,1000);
            INSERT INTO canonical_scheduler VALUES(1,4);
            INSERT INTO worker_meta VALUES(1,1,1,100);
            INSERT INTO matching_replay VALUES('t','source','descriptor','old');
        """)


def test_verifier_allows_new_maps_and_refuses_changed_old_rows(tmp_path):
    prior, current = tmp_path / "before.sqlite", tmp_path / "after.sqlite"
    ledger(prior)
    ledger(current)
    with sqlite3.connect(current) as db:
        db.execute("INSERT INTO canonical_episode VALUES('new',2,6)")
    assert VERIFY.compare(current, prior)["canonical_episode"]["added"] == 1
    for sql in (
        "UPDATE release SET first_seen_at=124",
        "UPDATE canonical_episode SET season=3 WHERE id='e'",
        "UPDATE work SET failures=0",
        "UPDATE worker_meta SET bootstrap_finished=0",
    ):
        with sqlite3.connect(current) as db:
            db.execute("BEGIN")
            db.execute(sql)
            # An independent read connection cannot see uncommitted changes.
            db.commit()
        with pytest.raises(ValueError, match="preservation failed"):
            VERIFY.compare(current, prior)
        current.unlink()
        ledger(current)


def test_verifier_checks_exact_fairness_advance_without_waiving_retry_history(tmp_path):
    prior, current = tmp_path / "before.sqlite", tmp_path / "after.sqlite"
    ledger(prior)
    ledger(current)
    with sqlite3.connect(current) as db:
        db.execute("UPDATE canonical_scheduler SET slot=0")
    with pytest.raises(ValueError, match="canonical_scheduler"):
        VERIFY.compare(current, prior)
    assert VERIFY.compare(current, prior, local_rematches=1)["canonical_scheduler"] == {
        "verified_local_rematches": 1
    }
    with pytest.raises(ValueError, match="advancement"):
        VERIFY.compare(current, prior, local_rematches=2)
    with sqlite3.connect(current) as db:
        db.execute("UPDATE work SET failures=0")
    with pytest.raises(ValueError, match="work"):
        VERIFY.compare(current, prior, local_rematches=1)


def test_receipt_updates_keep_input_fingerprints_and_publication_keeps_bootstrap(
    tmp_path,
):
    prior, current = tmp_path / "before.sqlite", tmp_path / "after.sqlite"
    ledger(prior)
    ledger(current)
    with sqlite3.connect(current) as db:
        db.execute("UPDATE canonical_scheduler SET slot=0")
        db.execute("UPDATE worker_meta SET dirty=0,published_at=200")
        db.execute("UPDATE matching_replay SET matcher='new'")
    assert (
        VERIFY.compare(current, prior, local_rematches=1)["matching_replay"][
            "changed_receipts"
        ]
        == 1
    )
    with sqlite3.connect(current) as db:
        db.execute("UPDATE matching_replay SET source_hash='unexpected'")
    with pytest.raises(ValueError, match="receipt"):
        VERIFY.compare(current, prior, local_rematches=1)
