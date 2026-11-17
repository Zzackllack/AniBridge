"""Durable file publication/ownership proof; synthetic URLs do not prove playback."""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from catalog_core.files import atomic_write
from catalog_core.json_codec import dumps

from app.catalog.executor import SubprocessExecutor
from app.catalog.output_publication import publish
from app.catalog.jobs import Jobs
from test_jobs import setup_jobs, grab, NOW

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="snapshot runtime requires Linux enforcement"
)


class FixtureExecutor(SubprocessExecutor):
    def __init__(self, root, *, outcome="ok", mode="direct"):
        super().__init__(
            {"aniworld.to": "https://provider.invalid"}, ("VOE",), root, strm_mode=mode
        )
        self.calls, self.outcome = [], outcome

    async def _run(self, module, arguments, **options):
        self.calls.append(module)
        if module == "app.catalog.resolve_child":
            atomic_write(
                Path(arguments[1]),
                dumps(
                    {
                        "phase": "finished",
                        "outcome": self.outcome,
                        "url": "https://media.invalid/generated?token=fixture",
                        "host": "VOE",
                    }
                ),
            )
            return 0
        return await super()._run(module, arguments, **options)


def request(jobs, uri):
    job = jobs.admit(uri, NOW)[0]
    claim = jobs.claim(NOW)
    payload = json.loads(claim["payload"])
    payload.update(job_id=job, generation=claim["generation"])
    return job, claim, payload


def configure_proxy(monkeypatch, secret):
    from app.catalog import strm_http

    # Legacy client fixtures unload auth modules. Patch the globals actually
    # bound to this route, rather than a newly imported module with stale peers.
    monkeypatch.setitem(
        strm_http.build_auth_params.__globals__, "STRM_PROXY_AUTH", "token"
    )
    monkeypatch.setitem(
        strm_http.build_auth_params.__globals__, "STRM_PROXY_SECRET", secret
    )
    monkeypatch.setitem(
        strm_http._build_url.__globals__, "STRM_PUBLIC_BASE_URL", "http://local.invalid"
    )


def test_direct_strm_is_verified_before_completion_and_survives_restart(tmp_path):
    jobs = setup_jobs(tmp_path)
    job, claim, payload = request(jobs, grab(tmp_path, "strm"))
    executor = FixtureExecutor(jobs.download_dir)
    outcome = asyncio.run(executor(payload, lambda _: None))
    assert outcome.code == "ok" and outcome.output.suffix == ".strm"
    assert (
        outcome.output.read_text() == "https://media.invalid/generated?token=fixture\n"
    )
    assert executor.calls == ["app.catalog.resolve_child", "app.catalog.output_receipt"]
    assert outcome.evidence is None
    assert jobs.finish(job, claim["generation"], outcome.code, NOW + 1, outcome.output)
    restarted = Jobs(jobs.filename, jobs.download_dir, jobs.providers)
    restarted.recover(NOW + 10)
    assert restarted.get(job)["status"] == "completed"
    assert restarted.projection(job)["progress"] == 1
    # Interrupted completion can reuse only the bound receipt, without resolving.
    executor.calls.clear()
    reused = asyncio.run(executor(payload, lambda _: None))
    assert reused.output == outcome.output and executor.calls == [
        "app.catalog.output_receipt"
    ]
    outcome.output.write_text("Changed by another local process")
    assert asyncio.run(executor(payload, lambda _: None)).code == "output_conflict"


def test_strm_challenge_remains_blocked_and_pause_wins_file_completion(tmp_path):
    jobs = setup_jobs(tmp_path)
    job, claim, payload = request(jobs, grab(tmp_path, "strm"))
    executor = FixtureExecutor(jobs.download_dir, outcome="challenge")
    outcome = asyncio.run(executor(payload, lambda _: None))
    assert outcome.code == "challenge" and outcome.output is None
    jobs.finish(job, claim["generation"], outcome.code, NOW + 1)
    restarted = Jobs(jobs.filename, jobs.download_dir, jobs.providers)
    restarted.recover(NOW + 100)
    assert (
        restarted.get(job)["status"] == "blocked" and restarted.claim(NOW + 100) is None
    )
    restarted.action(job, "retry", NOW + 101)
    claim = restarted.claim(NOW + 102)
    payload.update(generation=claim["generation"])
    executor.outcome = "ok"
    outcome = asyncio.run(executor(payload, lambda _: None))
    restarted.action(job, "pause", NOW + 103)
    assert not restarted.finish(
        job, claim["generation"], outcome.code, NOW + 104, outcome.output
    )
    assert restarted.get(job)["status"] == "paused"
    assert outcome.output.exists()


def test_proxy_file_is_stable_signed_and_resolves_only_after_admission(
    tmp_path, monkeypatch
):
    from app.catalog import strm_http
    from urllib.parse import parse_qs, urlsplit

    configure_proxy(monkeypatch, "generated secret")
    jobs = setup_jobs(tmp_path)
    jobs.strm_mode = "proxy"
    job, claim, payload = request(jobs, grab(tmp_path, "strm"))
    executor = FixtureExecutor(jobs.download_dir, mode="proxy")
    outcome = asyncio.run(executor(payload, lambda _: None))
    assert outcome.code == "ok" and outcome.output.suffix == ".strm"
    parsed = urlsplit(outcome.output.read_text().strip())
    params = {key: values[0] for key, values in parse_qs(parsed.query).items()}
    assert parsed.path == "/strm/catalog" and params["job"] == job
    assert "u" not in params and "exp" not in params
    strm_http.require_auth(params, scope="catalog-playback-1")
    assert executor.calls == ["app.catalog.resolve_child", "app.catalog.output_receipt"]
    assert jobs.finish(job, claim["generation"], outcome.code, NOW + 1, outcome.output)
    restarted = Jobs(jobs.filename, jobs.download_dir, jobs.providers)
    restarted.recover(NOW + 2)
    assert restarted.get(job)["status"] == "completed"


def test_publication_cannot_overwrite_racing_file_or_symlink(tmp_path):
    staged, target, user = tmp_path / "staged", tmp_path / "target", tmp_path / "user"
    staged.write_bytes(b"verified")
    user.write_bytes(b"preserved")
    target.symlink_to(user)
    with pytest.raises(FileExistsError):
        publish(staged, target)
    assert user.read_bytes() == b"preserved" and staged.exists()
    target.unlink()
    target.write_bytes(b"another writer")
    with pytest.raises(FileExistsError):
        publish(staged, target)
    assert target.read_bytes() == b"another writer" and staged.exists()


def test_proxy_completion_registration_requires_winning_generation(
    tmp_path, monkeypatch
):
    from app.catalog.strm_http import Playback
    from fastapi import HTTPException

    configure_proxy(monkeypatch, "generated key")
    jobs = setup_jobs(tmp_path)
    jobs.strm_mode = "proxy"
    uri = grab(tmp_path, "strm")
    job, claim, payload = request(jobs, uri)
    # A configuration change after admission cannot convert the frozen delivery.
    restarted = Jobs(
        jobs.filename, jobs.download_dir, jobs.providers, strm_mode="direct"
    )
    assert restarted.admit(uri, NOW + 1) == [job]
    assert json.loads(restarted.get(job)["payload"])["strm_delivery"] == "proxy"
    executor = FixtureExecutor(jobs.download_dir, mode="direct")
    outcome = asyncio.run(executor(payload, lambda _: None))
    assert outcome.code == "ok" and "/strm/catalog?" in outcome.output.read_text()
    restarted.action(job, "pause", NOW + 2)
    assert not restarted.finish(job, claim["generation"], "ok", NOW + 3, outcome.output)
    playback = Playback(None, restarted, {}, ())
    with pytest.raises(HTTPException) as error:
        playback.accepted(job)
    assert error.value.status_code == 409
    restarted.action(job, "resume", NOW + 4)
    winning = restarted.claim(NOW + 5)
    assert restarted.finish(job, winning["generation"], "ok", NOW + 6, outcome.output)
    assert playback.accepted(job)["strm_delivery"] == "proxy"
    # Registration binds the exact frozen payload; a changed private request
    # cannot reuse previously accepted playback authority.
    with restarted.db() as db:
        db.execute("UPDATE durable_request SET payload=? WHERE job_id=?", ("{}", job))
    with pytest.raises(HTTPException):
        playback.accepted(job)
