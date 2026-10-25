"""Canonical failures retain evidence/history and report only bounded codes."""

import asyncio
import json

import pytest
from catalog_core.providers.transport import Fetch
from test_canonical import NOW, ready

from catalog_worker.canonical import Enricher
from catalog_worker.canonical_failures import Failure
from catalog_worker.events import Events


@pytest.mark.parametrize(
    ("response", "reason", "status"),
    [
        (Fetch("rate_limited", status=429, retry_after=600), "rate_limited", 429),
        (Fetch("http_error", status=500), "http_error", 500),
        (Fetch("challenge_or_block", status=403), "challenge_or_block", 403),
        (Fetch("ok", b"private HTML token=secret", status=200), "invalid_json", 200),
        (Fetch("ok", b"{}", status=200), "invalid_payload", None),
    ],
)
def test_lookup_reports_failure_after_retry_is_persisted(
    tmp_path, response, reason, status
):
    state = ready(tmp_path)
    before = list(state.db.execute("SELECT * FROM work"))
    reports = []

    async def fetch(*args, **kwargs):
        return response

    def observe(provider, tid, failure):
        row = state.db.execute(
            "SELECT * FROM mapping_input WHERE title_id=?", (tid,)
        ).fetchone()
        assert row["failures"] == 1 and row["outcome"] == "source_failure"
        assert row["next_due"] == NOW + max(300, response.retry_after or 0)
        reports.append((provider, failure))

    enricher = Enricher({}, fetcher=fetch, on_failure=observe)
    assert asyncio.run(enricher.tick(state, NOW))
    assert reports == [("aniworld.to", Failure("search", reason, status))]
    assert list(state.db.execute("SELECT * FROM work")) == before
    assert not state.db.execute("SELECT 1 FROM canonical_title").fetchone()
    assert not asyncio.run(enricher.tick(state, NOW + 1))
    assert enricher.last_failure is None  # Idle ticks must not repeat a stale failure.
    assert len(reports) == 1
    state.close()


@pytest.mark.parametrize("phase", ["descriptor", "translation"])
def test_http_success_with_wrong_identity_has_its_own_code(tmp_path, phase):
    state = ready(tmp_path)
    reports = []

    async def fetch(origin, path, **kwargs):
        item = {
            "tvdbId": 123,
            "title": "Example",
            "year": 2020,
            "episodes": [],
            "metadataSource": "tvdb",
            "language": "deu" if "/deu/" in path else "eng",
        }
        if (phase == "descriptor" and "/eng/" in path) or (
            phase == "translation" and "/deu/" in path
        ):
            item["tvdbId"] = 456
        return Fetch(
            "ok", json.dumps([item] if "search" in path else item).encode(), status=200
        )

    enricher = Enricher(
        {"episode_languages": ["deu"]},
        fetcher=fetch,
        on_failure=lambda p, t, f: reports.append(f),
    )
    assert asyncio.run(enricher.tick(state, NOW))
    assert reports == [
        Failure(
            phase,
            "parent_id_mismatch"
            if phase == "descriptor"
            else "translation_identity_conflict",
        )
    ]
    assert not state.db.execute("SELECT 1 FROM canonical_title").fetchone()
    state.close()


def test_admission_is_not_a_canonical_failure(tmp_path):
    state = ready(tmp_path)
    enricher = Enricher(
        {},
        clock=lambda: NOW,
        on_failure=lambda *args: pytest.fail("budget wait reported"),
    )
    enricher.starts.extend([NOW] * 30)
    before = dict(state.db.execute("SELECT * FROM mapping_input").fetchone())
    assert not asyncio.run(enricher.tick(state, NOW))
    assert enricher.last_failure is None
    assert dict(state.db.execute("SELECT * FROM mapping_input").fetchone()) == before
    state.close()


@pytest.mark.parametrize("parent", [None, ["invalid"], {"year": 2020}])
def test_invalid_cached_parent_is_reacquired_without_losing_history(tmp_path, parent):
    state = ready(tmp_path)
    calls = []

    async def fetch(origin, path, **kwargs):
        calls.append(path)
        item = {"tvdbId": 123, "title": "Example", "year": 2020, "episodes": []}
        return Fetch("ok", json.dumps([item] if "search" in path else item).encode())

    worker = Enricher({}, fetcher=fetch, clock=lambda: NOW)
    try:
        assert asyncio.run(worker.tick(state, NOW))
        payload = json.loads(
            state.db.execute("SELECT payload FROM canonical_descriptor").fetchone()[0]
        )
        if parent is None:
            del payload["parent"]
        else:
            payload["parent"] = parent
        with state.db:
            state.db.execute(
                "UPDATE canonical_descriptor SET payload=?", (json.dumps(payload),)
            )
            state.db.execute("UPDATE mapping_input SET next_due=?", (NOW + 1,))
        before = list(state.db.execute("SELECT * FROM work"))
        calls.clear()
        worker = Enricher({}, fetcher=fetch, clock=lambda: NOW + 1)
        assert asyncio.run(worker.tick(state, NOW + 1))
        assert len(calls) == 1
        assert list(state.db.execute("SELECT * FROM work")) == before
        result = state.db.execute("SELECT * FROM mapping_input").fetchone()
        assert result["failures"] == 0 and result["next_due"] > NOW + 1
        repaired = json.loads(
            state.db.execute("SELECT payload FROM canonical_descriptor").fetchone()[0]
        )
        assert repaired["parent"] == {"names": ["Example"], "year": 2020, "imdb": None}
    finally:
        state.close()


def test_private_parent_accepts_all_bounded_descriptor_and_search_aliases(tmp_path):
    from catalog_worker.parent_evidence import status

    state = ready(tmp_path)

    async def fetch(origin, path, **kwargs):
        item = {"tvdbId": 123, "title": "Example", "year": 2020, "episodes": []}
        if "search" in path:
            item["aliases"] = [f"Search alias {n}" for n in range(100)]
        else:
            item["originalTitle"] = "Original"
            for field in ("aliases", "alternativeTitles", "translations"):
                item[field] = [f"{field} alias {n}" for n in range(100)]
        return Fetch("ok", json.dumps([item] if "search" in path else item).encode())

    try:
        assert asyncio.run(Enricher({}, fetcher=fetch).tick(state, NOW))
        tid = state.db.execute("SELECT title_id FROM title").fetchone()[0]
        assert status(state, tid, "123", "exact_title_year") == "verified"
    finally:
        state.close()


@pytest.mark.parametrize("descriptor_year", [2020, 2022])
@pytest.mark.parametrize(
    "remote_parent",
    [["unexpected"], {"names": ["Example"], "year": 2020, "imdb": None}],
)
def test_remote_descriptor_cannot_supply_private_parent_proof(
    tmp_path, descriptor_year, remote_parent
):
    state = ready(tmp_path)

    async def fetch(origin, path, **kwargs):
        item = {"tvdbId": 123, "title": "Example", "year": 2020, "episodes": []}
        if "search" not in path:
            item.update(year=descriptor_year, parent=remote_parent)
        return Fetch("ok", json.dumps([item] if "search" in path else item).encode())

    worker = Enricher({}, fetcher=fetch, clock=lambda: NOW)
    try:
        assert asyncio.run(worker.tick(state, NOW))
        result = state.db.execute("SELECT * FROM mapping_input").fetchone()
        assert result["outcome"] == (
            "matched" if descriptor_year == 2020 else "conflict"
        )
        assert result["failures"] == 0
        assert bool(state.db.execute("SELECT 1 FROM canonical_title").fetchone()) == (
            descriptor_year == 2020
        )
        saved = json.loads(
            state.db.execute("SELECT payload FROM canonical_descriptor").fetchone()[0]
        )
        assert saved["parent"]["year"] == descriptor_year
        assert not asyncio.run(worker.tick(state, NOW + 1))
    finally:
        state.close()


@pytest.mark.parametrize(
    "invalid",
    [{"tvdbId": [456]}, {"seasonNumber": 2**63}, {"episodeNumber": 2**63}],
)
def test_malformed_episode_retains_retry_instead_of_stopping_worker(tmp_path, invalid):
    state = ready(tmp_path)
    before = list(state.db.execute("SELECT * FROM work"))

    async def fetch(origin, path, **kwargs):
        item = {"tvdbId": 123, "title": "Example", "year": 2020, "episodes": []}
        if "search" not in path:
            item["episodes"] = [
                {
                    "seasonNumber": 1,
                    "episodeNumber": 1,
                    "title": "One",
                    "tvdbId": 456,
                    **invalid,
                }
            ]
        return Fetch("ok", json.dumps([item] if "search" in path else item).encode())

    worker = Enricher({}, fetcher=fetch, clock=lambda: NOW)
    try:
        assert asyncio.run(worker.tick(state, NOW))
        result = state.db.execute("SELECT * FROM mapping_input").fetchone()
        assert result["outcome"] == "source_failure" and result["failures"] == 1
        assert result["next_due"] == NOW + 300
        assert list(state.db.execute("SELECT * FROM work")) == before
        assert not state.db.execute("SELECT 1 FROM canonical_title").fetchone()
        assert not asyncio.run(worker.tick(state, NOW + 1))
    finally:
        state.close()


def test_failure_log_rejects_untrusted_fields(tmp_path):
    events = Events(tmp_path)
    events.canonical_failure(
        "s.to", "a" * 64, Failure("translation", "episode_parent_conflict")
    )
    events.canonical_failure(
        "s.to", "private term token=secret", Failure("private URL", "private HTML", 999)
    )
    events.canonical_failure(
        "private provider", "a" * 64, Failure("search", "invalid_json")
    )
    events.close()
    text = (tmp_path / "worker.jsonl").read_text()
    first, second = [json.loads(line) for line in text.splitlines()]
    assert (
        first["title_id"] == "a" * 64 and first["reason"] == "episode_parent_conflict"
    )
    assert second["title_id"] is None and second["phase"] == "unknown"
    assert second["reason"] == "invalid_payload" and second["http_status"] is None
    assert not any(value in text for value in ("private", "secret", "HTML", "URL"))
