import sqlite3

import pytest
from app.catalog.jobs import JobError, Jobs, decode
from app.catalog.state_schema import STATEMENTS
from catalog_core import fixtures, magnet, schema

NOW = 1800000000


@pytest.mark.parametrize("failure_stage", ["recover", "finish"])
def test_runner_retries_storage_transaction_without_reexecuting_job(
    tmp_path, monkeypatch, failure_stage
):
    import asyncio
    from app.catalog.runner import Runner, Outcome
    from app.catalog.child_budget import ChildBudget

    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    calls, transactions = [], []
    original = getattr(jobs, failure_stage)

    def transaction(*args, **kwargs):
        transactions.append(True)
        if len(transactions) == 1:
            raise sqlite3.OperationalError("injected disk full")
        return original(*args, **kwargs)

    monkeypatch.setattr(jobs, failure_stage, transaction)

    async def execute(payload, progress):
        calls.append(payload["job_id"])
        return Outcome("challenge")

    async def scenario():
        budget = ChildBudget()
        runner = Runner(jobs, execute, clock=lambda: NOW, children=budget)
        task = asyncio.create_task(runner.run())
        try:
            async with asyncio.timeout(4):
                while (
                    jobs.get(job)["status"] != "blocked"
                    or runner.running
                    or budget.active
                ):
                    assert not task.done()
                    await asyncio.sleep(0.02)
            assert calls == [job]
            assert len(transactions) >= 2
            assert not runner.running and not budget.active
            assert jobs.get(job)["attempts"] == 1
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


def setup_jobs(tmp_path):
    database = tmp_path / "private.sqlite"
    with sqlite3.connect(database) as db:
        db.execute("""CREATE TABLE job(id TEXT PRIMARY KEY,status TEXT,progress REAL,downloaded_bytes INTEGER,
            total_bytes INTEGER,speed REAL,eta INTEGER,message TEXT,result_path TEXT,source_site TEXT,
            created_at TEXT,updated_at TEXT)""")
        db.execute("""CREATE TABLE clienttask(hash TEXT PRIMARY KEY,name TEXT,slug TEXT,season INTEGER,episode INTEGER,
            language TEXT,site TEXT,job_id TEXT,save_path TEXT,category TEXT,added_on TEXT,completion_on TEXT,state TEXT)""")
        for statement in STATEMENTS:
            db.execute(statement)
    (tmp_path / "downloads").mkdir()
    return Jobs(database, tmp_path / "downloads", {"aniworld.to", "s.to", "megakino"})


def grab(tmp_path, mode="download"):
    fixtures.build(tmp_path / "fixture")
    db = schema.connect(tmp_path / "fixture/fixture.sqlite")
    t = dict(db.execute("SELECT * FROM title").fetchone())
    e = dict(db.execute("SELECT * FROM entity").fetchone())
    r = dict(db.execute("SELECT * FROM release WHERE language='de-dub'").fetchone())
    db.close()
    return magnet.encode(
        {
            "provider": "aniworld.to",
            "title_id": t["title_id"],
            "entity_id": e["entity_id"],
            "release_id": r["release_id"],
            "title_anchor": t["identity_anchor"],
            "entity_anchor": e["identity_anchor"],
            "slug": t["slug"],
            "path": e["path"],
            "kind": "episode",
            "native_season": 1,
            "native_episode": 2,
            "language": "de-dub",
            "mode": mode,
            "canonical": None,
        },
        "Example.S01E02.German.Dub",
    )


def test_paused_add_duplicate_restart_and_blocked_projection(tmp_path):
    jobs = setup_jobs(tmp_path)
    value = grab(tmp_path)
    job = jobs.admit(value, NOW, paused=True)[0]
    assert jobs.claim(NOW) is None
    assert jobs.admit(value, NOW + 1, paused=False) == [job]
    assert jobs.get(job)["status"] == "paused"
    jobs.action(job, "resume", NOW + 2)
    claimed = jobs.claim(NOW + 3)
    assert jobs.finish(job, claimed["generation"], "challenge", NOW + 4)
    assert jobs.projection(job)["state"] == "stalledDL"
    assert jobs.projection(job)["progress"] < 1
    assert jobs.projection(job)["content_path"] == ""
    restarted = Jobs(jobs.filename, jobs.download_dir, jobs.providers)
    restarted.recover(NOW + 1000)
    assert restarted.get(job)["status"] == "blocked"
    assert restarted.claim(NOW + 1000) is None


def test_pause_and_cancel_win_late_completion(tmp_path):
    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    claimed = jobs.claim(NOW)
    paused = jobs.action(job, "pause", NOW + 1)
    output = jobs.download_dir / "test.mkv"
    output.write_bytes(b"synthetic test bytes")
    assert not jobs.finish(job, claimed["generation"], "ok", NOW + 2, output)
    assert jobs.get(job)["status"] == "paused"
    with pytest.raises(JobError) as exc:
        jobs.action(job, "cancel", NOW + 3, paused["version"] - 1)
    assert exc.value.status == 412
    jobs.action(job, "cancel", NOW + 4, paused["version"])
    assert jobs.get(job)["status"] == "cancelled"
    assert not jobs.finish(job, claimed["generation"], "ok", NOW + 5, output)
    version = jobs.get(job)["version"]
    assert jobs.action(job, "cancel", NOW + 6)["version"] == version


def test_batch_atomicity_and_hash_conflict(tmp_path):
    jobs = setup_jobs(tmp_path)
    value = grab(tmp_path)
    with pytest.raises(ValueError):
        jobs.admit(value + "\nnot-a-magnet", NOW)
    with sqlite3.connect(jobs.filename) as db:
        assert db.execute("SELECT count(*) FROM job").fetchone()[0] == 0
    legacy = (
        "magnet:?xt=urn:btih:"
        + 40 * "a"
        + "&dn=Example&aw_slug=example&aw_s=1&aw_e=2&aw_lang=German+Dub"
    )
    job = jobs.admit(legacy, NOW)[0]
    with pytest.raises(JobError, match="identity_conflict"):
        jobs.admit(legacy + "&aw_site=megakino", NOW + 1)
    assert jobs.get(job)["hashes"] == [40 * "a"]


def test_restart_consumes_attempt_budget_and_retry_is_explicit(tmp_path):
    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    for offset in (0, 121, 482):
        claimed = jobs.claim(NOW + offset)
        assert claimed
        jobs.recover(NOW + offset + 61)
    row = jobs.get(job)
    assert row["status"] == "failed" and row["error_code"] == "retry_exhausted"
    jobs.action(job, "retry", NOW + 1000, row["version"])
    assert jobs.get(job)["attempts"] == 0
    claimed = jobs.claim(NOW + 1000)
    jobs.finish(job, claimed["generation"], "challenge", NOW + 1001)
    with pytest.raises(JobError, match="rate_limited"):
        jobs.action(job, "retry", NOW + 1002)


def test_capacity_and_disabled_provider(tmp_path):
    jobs = setup_jobs(tmp_path)
    jobs.queue_limit = 1
    value = grab(tmp_path)
    job = jobs.admit(value, NOW)[0]
    assert jobs.admit(value, NOW) == [job]
    _digest, payload, label, _ = decode(value)
    payload["mode"] = "strm"
    with pytest.raises(JobError, match="queue_full"):
        jobs.admit(magnet.encode(payload, label), NOW)
    jobs.providers = set()
    assert jobs.claim(NOW) is None
    assert jobs.get(job)["status"] == "paused"


def test_runner_pause_cancel_and_restart_do_not_reexecute_blocked(tmp_path):
    import asyncio
    from app.catalog.runner import Outcome, Runner

    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW, paused=True)[0]
    calls, stopped = [], []

    async def execute(payload, progress):
        calls.append(payload["job_id"])
        progress({"downloaded_bytes": 50, "total_bytes": 100, "speed": 10})
        try:
            await asyncio.Event().wait()
        finally:
            stopped.append(payload["job_id"])

    async def scenario():
        runner = Runner(jobs, execute, clock=lambda: NOW)
        await runner.tick()
        assert calls == []
        jobs.action(job, "resume", NOW)
        await runner.tick()
        await asyncio.sleep(0)
        assert jobs.get(job)["status"] == "downloading"
        jobs.action(job, "pause", NOW + 1)
        await runner.tick()
        await asyncio.sleep(0)
        await runner.tick()
        assert stopped == [job]
        assert jobs.get(job)["status"] == "paused"
        assert jobs.get(job)["downloaded_bytes"] == 50
        await runner.close()
        assert jobs.get(job)["status"] == "paused"

        async def blocked(payload, progress):
            return Outcome("challenge")

        jobs.action(job, "resume", NOW + 2)
        runner = Runner(jobs, blocked, clock=lambda: NOW + 2)
        await runner.tick()
        await asyncio.sleep(0)
        await runner.tick()
        assert jobs.get(job)["status"] == "blocked"
        await runner.close()
        jobs.recover(NOW + 100, startup=True)
        assert jobs.get(job)["status"] == "blocked"
        assert jobs.get(job)["downloaded_bytes"] == 50
        assert jobs.projection(job)["progress"] == 0.5

    asyncio.run(scenario())


def test_restart_consumes_attempt_and_missing_output_never_redownloads(tmp_path):
    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    jobs.claim(NOW)
    assert jobs.get(job)["attempts"] == 1
    jobs.recover(NOW + 1, startup=True)
    assert jobs.get(job)["status"] == "retry_wait"
    assert jobs.claim(NOW + 2) is None
    second = jobs.claim(NOW + 61)
    output = jobs.download_dir / "generated.mkv"
    output.write_bytes(b"synthetic result fixture")
    assert jobs.finish(job, second["generation"], "ok", NOW + 62, output)
    output.unlink()
    jobs.recover(NOW + 63, startup=True)
    assert jobs.get(job)["status"] == "failed"
    assert jobs.get(job)["error_code"] == "missing_output"
    assert jobs.claim(NOW + 1000) is None


def test_duplicate_remains_idempotent_at_disk_ceiling(tmp_path):
    jobs = setup_jobs(tmp_path)
    value = grab(tmp_path)
    job = jobs.admit(value, NOW, paused=True)[0]
    jobs.metadata_limit = 1
    assert jobs.admit(value, NOW + 1) == [job]
    _, payload, label, _ = decode(value)
    payload["mode"] = "strm"
    with pytest.raises(ValueError, match="storage_full"):
        jobs.admit(magnet.encode(payload, label), NOW + 2)
    assert jobs.get(job)["status"] == "paused"


def test_incomplete_legacy_request_conservatively_retains_download_tree(tmp_path):
    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW, paused=True)[0]
    with sqlite3.connect(jobs.filename) as db:
        db.execute("UPDATE job SET status='failed' WHERE id=?", (job,))
        db.execute(
            "UPDATE durable_request SET payload=?,error_code='legacy_request_incomplete' WHERE job_id=?",
            ('{"legacy":true,"incomplete":true,"mode":null}', job),
        )
    assert jobs.retained_directories() == {jobs.download_dir}
    assert jobs.get(job)["error_code"] == "legacy_request_incomplete"


def test_pause_cannot_undo_cancellation_in_flight(tmp_path):
    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    claim = jobs.claim(NOW)
    cancelled = jobs.action(job, "cancel", NOW + 1)
    assert cancelled["status"] == "cancelling"
    assert jobs.action(job, "pause", NOW + 2)["status"] == "cancelling"
    assert jobs.action(job, "resume", NOW + 3)["status"] == "cancelling"
    assert not jobs.finish(job, claim["generation"], "challenge", NOW + 4)
    jobs.settle_cancel(job, NOW + 5)
    assert jobs.get(job)["status"] == "cancelled"


def test_runner_does_not_consume_attempt_until_child_budget_available(tmp_path):
    import asyncio
    from app.catalog.child_budget import ChildBudget
    from app.catalog.runner import Runner

    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    budget = ChildBudget()
    leases = [budget.try_acquire("validation"), budget.try_acquire("download")]

    async def execute(payload, progress):
        await asyncio.Event().wait()

    async def scenario():
        runner = Runner(jobs, execute, clock=lambda: NOW, children=budget)
        await runner.tick()
        assert jobs.get(job)["attempts"] == 0
        assert jobs.get(job)["status"] == "queued"
        leases[0].close()
        await runner.tick()
        assert jobs.get(job)["attempts"] == 1
        # Cancel before the executor gets its first event-loop turn. The runner
        # still owns/releases its slot even though no coroutine finally ran.
        await runner.close()
        assert len(budget.active) == 1
        leases[1].close()
        assert not budget.active

    asyncio.run(scenario())


def test_runner_releases_budget_on_corrupt_payload_and_executor_failure(tmp_path):
    import asyncio
    from app.catalog.child_budget import ChildBudget
    from app.catalog.runner import Runner

    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    budget = ChildBudget()

    async def execute(payload, progress):
        raise RuntimeError("synthetic executor failure")

    async def scenario():
        runner = Runner(jobs, execute, clock=lambda: NOW, children=budget)
        await runner.tick()
        await asyncio.sleep(0)
        await runner.tick()
        assert jobs.get(job)["status"] == "failed"
        assert not budget.active
        jobs.action(job, "retry", NOW + 301)
        with sqlite3.connect(jobs.filename) as db:
            db.execute("UPDATE durable_request SET payload='[]' WHERE job_id=?", (job,))
        await runner.tick()
        assert jobs.get(job)["status"] == "failed"
        assert not budget.active
        await runner.close()

    asyncio.run(scenario())


def test_alias_removal_intent_survives_restart_and_preserves_files(tmp_path):
    from app.catalog.client import ClientJobs

    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    claim = jobs.claim(NOW)
    output = jobs.download_dir / "generated.mkv"
    output.write_bytes(b"generated local output fixture")
    jobs.finish(job, claim["generation"], "ok", NOW + 1, output)
    client = ClientJobs(jobs, "/public/downloads")
    alias = client.aliases()[0]
    view = client.view(alias)
    assert view["content_path"] == "/public/downloads/generated.mkv"
    assert view["completion_on"] > 0
    client.remove(alias["hash"], False, NOW + 2)
    # Simulated restart after intent+cancel, before alias deletion.
    restarted = ClientJobs(Jobs(jobs.filename, jobs.download_dir, jobs.providers))
    restarted.settle_removals(set(), NOW + 3)
    assert not restarted.aliases()
    assert output.read_bytes() == b"generated local output fixture"
    assert jobs.get(job)["status"] == "cancelled"


def test_alias_removal_waits_for_child_and_rechecks_output_containment(tmp_path):
    from app.catalog.client import ClientJobs

    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    jobs.claim(NOW)
    client = ClientJobs(jobs)
    alias = client.aliases()[0]
    outside = tmp_path / "private.txt"
    outside.write_text("preserve")
    with sqlite3.connect(jobs.filename) as db:
        db.execute("UPDATE job SET result_path=? WHERE id=?", (str(outside), job))
    client.remove(alias["hash"], True, NOW + 1)
    client.settle_removals({job}, NOW + 2)
    assert client.aliases()
    assert jobs.get(job)["status"] == "cancelling"
    client.settle_removals(set(), NOW + 3)
    assert not client.aliases()
    assert outside.read_text() == "preserve"


@pytest.mark.parametrize(
    "value, expected",
    [
        ("True", True),
        ("False", False),
        ("true", True),
        ("false", False),
        ("1", True),
        ("0", False),
    ],
)
def test_qbit_boolean_forms_accept_dotnet_client_spelling(value, expected):
    from app.catalog.qbit_http import boolean

    assert boolean(value) is expected


def test_ttl_retains_paused_blocked_cancelled_job_directories(tmp_path):
    import json
    from app.catalog.output_paths import output_paths

    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW, paused=True)[0]
    payload = json.loads(jobs.get(job)["payload"])
    root, _ = output_paths(payload, job)
    assert root in jobs.retained_directories()
    jobs.action(job, "resume", NOW + 1)
    claim = jobs.claim(NOW + 2)
    jobs.finish(job, claim["generation"], "challenge", NOW + 3)
    assert root in jobs.retained_directories()
    jobs.action(job, "cancel", NOW + 4)
    assert root in jobs.retained_directories()


def test_admission_freezes_host_policy_across_duplicate_and_restart(tmp_path):
    import json

    jobs = setup_jobs(tmp_path)
    jobs.hosts = ("VOE", "Filemoon")
    value = grab(tmp_path)
    job = jobs.admit(value, NOW, paused=True)[0]
    restarted = Jobs(
        jobs.filename, jobs.download_dir, jobs.providers, hosts=("Filemoon",)
    )
    assert restarted.admit(value, NOW + 1) == [job]
    assert json.loads(restarted.get(job)["payload"])["host_preference"] == [
        "VOE",
        "Filemoon",
    ]


def test_complete_legacy_tv_request_freezes_native_path_and_host_policy(tmp_path):
    import json
    from app.catalog.jobs import Jobs, decode

    fixture = setup_jobs(tmp_path)
    jobs = Jobs(
        fixture.filename,
        fixture.download_dir,
        {"aniworld.to", "s.to"},
        hosts=("VOE", "Doodstream"),
    )
    value = (
        "magnet:?xt=urn:btih:"
        + "a" * 40
        + "&aw_slug=example&aw_s=0&aw_e=2&aw_lang=German+Dub&aw_provider=Doodstream"
    )
    job = jobs.admit(value, NOW)[0]
    payload = json.loads(jobs.get(job)["payload"])
    assert payload["path"] == "/anime/stream/example/filme/film-2"
    assert payload["host_preference"] == ["Doodstream", "VOE"]
    assert payload["canonical"] is None and payload["entity_id"] is None
    assert payload["legacy"] and payload["mode"] == "download"
    changed = Jobs(
        fixture.filename, fixture.download_dir, {"aniworld.to"}, hosts=("VOE",)
    )
    assert changed.admit(value, NOW + 1) == [job]
    assert json.loads(changed.get(job)["payload"])["host_preference"] == [
        "Doodstream",
        "VOE",
    ]
    _, sto, _, equivalent = decode(
        value.replace("aw_", "sto_").replace("aw_slug", "sto_slug")
    )
    assert sto["path"] == "/serie/example/staffel-0/episode-2" and equivalent is None


def test_download_observation_commits_only_with_current_completion(tmp_path):
    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    claim = jobs.claim(NOW)
    output = jobs.download_dir / "generated-fixture.mkv"
    output.write_bytes(b"synthetic file; no media or playback claim")
    evidence = {"height": 720, "codec": "h264", "host": "VOE", "variant": "fixture"}
    assert not jobs.finish(job, claim["generation"] + 1, "ok", NOW, output, evidence)
    with jobs.db() as db:
        assert (
            db.execute(
                "SELECT count(*) FROM catalog_cache WHERE kind='sample-observation'"
            ).fetchone()[0]
            == 0
        )
    assert jobs.finish(job, claim["generation"], "ok", NOW, output, evidence)
    restarted = type(jobs)(jobs.filename, jobs.download_dir, jobs.providers)
    assert restarted.get(job)["status"] == "completed"
    with jobs.db() as db:
        pending = db.execute(
            "SELECT body FROM catalog_cache WHERE kind='sample-observation'"
        ).fetchone()[0]
        assert "720" in pending and "https:" not in pending


def test_legacy_movie_freezes_proven_local_path_without_v2_identity(tmp_path):
    import json
    import hashlib
    from urllib.parse import urlencode

    jobs = setup_jobs(tmp_path)
    digest = hashlib.sha1(b"example|1|1|German Dub").hexdigest()
    uri = "magnet:?" + urlencode(
        {
            "xt": "urn:btih:" + digest,
            "aw_slug": "example",
            "aw_s": "1",
            "aw_e": "1",
            "aw_lang": "German Dub",
            "aw_site": "megakino",
        }
    )
    selected = "/films/123-example.html"
    job = jobs.admit(uri, NOW, paused=True, legacy_path=lambda _: selected)[0]
    saved = json.loads(jobs.get(job)["payload"])
    assert saved["path"] == selected and saved["kind"] == "movie"
    assert saved["entity_id"] is None and saved["canonical"] is None
    assert jobs.get(job)["hashes"] == [digest]
    assert jobs.admit(
        uri, NOW + 1, legacy_path=lambda _: "/films/456-example.html"
    ) == [job]
    assert json.loads(jobs.get(job)["payload"])["path"] == selected
    restarted = Jobs(jobs.filename, jobs.download_dir, jobs.providers)
    assert json.loads(restarted.get(job)["payload"])["path"] == selected
