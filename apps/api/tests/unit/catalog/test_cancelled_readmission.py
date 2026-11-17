import json
import sqlite3

import pytest
from app.catalog.client import ClientJobs
from app.catalog.jobs import JobError, Jobs, decode
from app.catalog.state_schema import STATEMENTS
from catalog_core import fixtures, magnet, schema

NOW = 1_800_000_000


def setup_jobs(tmp_path):
    database = tmp_path / "private.sqlite"
    with sqlite3.connect(database) as db:
        db.execute(
            """CREATE TABLE job(id TEXT PRIMARY KEY,status TEXT,progress REAL,downloaded_bytes INTEGER,
            total_bytes INTEGER,speed REAL,eta INTEGER,message TEXT,result_path TEXT,source_site TEXT,
            created_at TEXT,updated_at TEXT)"""
        )
        db.execute(
            """CREATE TABLE clienttask(hash TEXT PRIMARY KEY,name TEXT,slug TEXT,season INTEGER,episode INTEGER,
            language TEXT,site TEXT,job_id TEXT,save_path TEXT,category TEXT,added_on TEXT,completion_on TEXT,state TEXT)"""
        )
        for statement in STATEMENTS:
            db.execute(statement)
    (tmp_path / "downloads").mkdir()
    return Jobs(database, tmp_path / "downloads", {"aniworld.to", "s.to", "megakino"})


def grab(tmp_path):
    fixtures.build(tmp_path / "fixture")
    db = schema.connect(tmp_path / "fixture/fixture.sqlite")
    title = dict(db.execute("SELECT * FROM title").fetchone())
    entity = dict(db.execute("SELECT * FROM entity").fetchone())
    release = dict(
        db.execute("SELECT * FROM release WHERE language='de-dub'").fetchone()
    )
    db.close()
    return magnet.encode(
        {
            "provider": "aniworld.to",
            "title_id": title["title_id"],
            "entity_id": entity["entity_id"],
            "release_id": release["release_id"],
            "title_anchor": title["identity_anchor"],
            "entity_anchor": entity["identity_anchor"],
            "slug": title["slug"],
            "path": entity["path"],
            "kind": "episode",
            "native_season": 1,
            "native_episode": 2,
            "language": "de-dub",
            "mode": "download",
            "canonical": None,
        },
        "Example.S01E02.German.Dub",
    )


def test_removed_unpublished_job_is_readmitted_with_new_generation(tmp_path):
    jobs = setup_jobs(tmp_path)
    value = grab(tmp_path)
    job_id = jobs.admit(value, NOW)[0]
    original = jobs.get(job_id)
    original_payload = original["payload"]

    # Keep a realistic partial and retry bookkeeping across remove/re-add.
    with sqlite3.connect(jobs.filename) as db:
        db.execute(
            "UPDATE job SET progress=37,downloaded_bytes=370,total_bytes=1000 WHERE id=?",
            (job_id,),
        )
        db.execute(
            "UPDATE durable_request SET attempts=2,error_code='retry_exhausted',"
            "next_retry_at=?,last_retry_at=? WHERE job_id=?",
            (NOW + 60, NOW - 60, job_id),
        )

    client = ClientJobs(jobs)
    alias = client.aliases()[0]
    client.remove(alias["hash"], False, NOW + 1)
    with pytest.raises(JobError, match="removal_pending"):
        jobs.admit(value, NOW + 2)
    with sqlite3.connect(jobs.filename) as db:
        assert db.execute(
            "SELECT state FROM catalog_task WHERE type='remove_aliases'"
        ).fetchone() == ("queued",)

    client.settle_removals(set(), NOW + 3)
    assert not client.aliases()
    cancelled = jobs.get(job_id)
    assert cancelled["status"] == "cancelled"

    assert jobs.admit(value, NOW + 4, paused=True) == [job_id]
    readmitted = jobs.get(job_id)
    assert readmitted["status"] == "paused"
    assert readmitted["generation"] == cancelled["generation"] + 1
    assert readmitted["version"] > cancelled["version"]
    assert readmitted["created_at"] == original["created_at"]
    assert readmitted["payload"] == original_payload
    assert readmitted["progress"] == 37
    assert readmitted["downloaded_bytes"] == 370
    assert readmitted["total_bytes"] == 1000
    assert readmitted["attempts"] == 0
    assert readmitted["error_code"] is None
    assert readmitted["next_retry_at"] is None
    assert len(client.aliases()) == 1
    with sqlite3.connect(jobs.filename) as db:
        assert db.execute("SELECT count(*) FROM job").fetchone()[0] == 1

    jobs.action(job_id, "resume", NOW + 5)
    claim = jobs.claim(NOW + 6)
    assert claim["generation"] > readmitted["generation"]


def test_cancelled_alias_without_removal_intent_fails_clearly(tmp_path):
    jobs = setup_jobs(tmp_path)
    value = grab(tmp_path)
    job_id = jobs.admit(value, NOW)[0]
    jobs.action(job_id, "cancel", NOW + 1)

    with pytest.raises(JobError, match="cancelled_request") as exc:
        jobs.admit(value, NOW + 2)
    assert exc.value.status == 409
    assert jobs.get(job_id)["status"] == "cancelled"
    assert len(ClientJobs(jobs).aliases()) == 1


def test_equivalent_new_hash_does_not_attach_while_job_is_cancelling(
    tmp_path, monkeypatch
):
    jobs = setup_jobs(tmp_path)
    value = grab(tmp_path)
    job_id = jobs.admit(value, NOW)[0]
    jobs.claim(NOW)
    assert jobs.action(job_id, "cancel", NOW + 1)["status"] == "cancelling"

    _digest, payload, label, identity_key = decode(value)
    alternate_hash = "b" * 40
    assert alternate_hash != decode(value)[0]
    monkeypatch.setattr(
        "app.catalog.jobs.decode",
        lambda _: (alternate_hash, payload, label, identity_key),
    )

    with pytest.raises(JobError, match="removal_pending") as exc:
        jobs.admit("equivalent-magnet", NOW + 2)
    assert exc.value.status == 409
    assert jobs.get(job_id)["status"] == "cancelling"
    assert len(ClientJobs(jobs).aliases()) == 1
    with sqlite3.connect(jobs.filename) as db:
        assert db.execute("SELECT count(*) FROM clienttask").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM grab_alias").fetchone()[0] == 1


def test_cancelled_job_with_pending_intent_and_no_alias_is_not_reactivated(
    tmp_path,
):
    jobs = setup_jobs(tmp_path)
    value = grab(tmp_path)
    job_id = jobs.admit(value, NOW)[0]
    client = ClientJobs(jobs)
    alias = client.aliases()[0]
    client.remove(alias["hash"], False, NOW + 1)
    client.settle_removals(set(), NOW + 2)

    # Model a queued intent left by an inconsistent/older database state.
    with sqlite3.connect(jobs.filename) as db:
        db.execute(
            "INSERT INTO catalog_task VALUES(?, 'remove_aliases', 'queued', ?, 1, ?, ?)",
            (
                "pending-remove",
                json.dumps({"job_id": job_id, "hashes": [alias["hash"]]}),
                NOW + 3,
                NOW + 3,
            ),
        )

    with pytest.raises(JobError, match="removal_pending") as exc:
        jobs.admit(value, NOW + 4)
    assert exc.value.status == 409
    assert jobs.get(job_id)["status"] == "cancelled"
    with sqlite3.connect(jobs.filename) as db:
        assert db.execute(
            "SELECT state FROM catalog_task WHERE id='pending-remove'"
        ).fetchone() == ("queued",)


def test_published_then_removed_job_is_not_readmitted(tmp_path):
    jobs = setup_jobs(tmp_path)
    value = grab(tmp_path)
    job_id = jobs.admit(value, NOW)[0]
    claim = jobs.claim(NOW)
    output = jobs.download_dir / "published.mkv"
    output.write_bytes(b"published fixture")
    assert jobs.finish(job_id, claim["generation"], "ok", NOW + 1, output)

    client = ClientJobs(jobs)
    alias = client.aliases()[0]
    client.remove(alias["hash"], False, NOW + 2)
    client.settle_removals(set(), NOW + 3)
    published = jobs.get(job_id)
    assert published["status"] == "cancelled"
    assert published["progress"] == 100
    assert published["result_path"] == str(output)

    with pytest.raises(JobError, match="cancelled_request"):
        jobs.admit(value, NOW + 4)
    assert jobs.get(job_id)["status"] == "cancelled"
    assert not ClientJobs(jobs).aliases()
    assert output.read_bytes() == b"published fixture"
