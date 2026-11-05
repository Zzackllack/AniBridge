"""End-to-end metadata-to-durable-grab checks with a local Filmo publication."""

import asyncio
import json
import sqlite3
import sys
import xml.etree.ElementTree as ET
from contextlib import closing
from pathlib import Path

import httpx
from catalog_core import magnet, schema
from catalog_core.query_client import Cache, Client

from app.catalog.jobs import Jobs
from app.catalog.query_local import Search
from app.catalog.search import rss
from app.catalog.state_schema import STATEMENTS

WORKER_SOURCE = Path(__file__).resolve().parents[4] / "catalog-worker" / "src"
if str(WORKER_SOURCE) not in sys.path:
    sys.path.insert(0, str(WORKER_SOURCE))

from catalog_core.providers.filmo import parse  # noqa: E402
from catalog_worker.config import LIMITS, Config  # noqa: E402
from catalog_worker.query_server import create_app  # noqa: E402
from catalog_worker.read_catalog import publish  # noqa: E402
from catalog_worker.state import State  # noqa: E402

NOW = 1_800_000_000
TOKEN = "synthetic-filmo-query-token"


def _published_filmo(tmp_path: Path) -> Path:
    state_dir, output_dir = tmp_path / "worker-state", tmp_path / "published"
    state = State(state_dir / "filmo.to.sqlite", "filmo.to")
    movie_path = "/movies/variant-example"
    html = b"""<div class="movie-poster-grid-card"><a href="/movies/variant-example">Example</a></div>"""
    state.listing(parse(html, "listing", "/movies"), NOW)
    detail = b"""<h1>Example Film</h1>
      <div class="provider-row"><span class="provider-row__lang">English Dub German Sub</span>
        <div data-provider-chip aria-label="VOE" data-movie-link-id="42" data-p="fixture-token-voe">
          <span class="provider-chip__metadata-tag">BluRay</span><span class="provider-chip__metadata-tag">720p</span>
        </div>
        <div data-provider-chip aria-label="Byse" data-movie-link-id="84" data-p="fixture-token-byse">
          <span class="provider-chip__metadata-tag">WEB</span><span class="provider-chip__metadata-tag">1080p</span>
        </div>
      </div>"""
    try:
        state.detail(state.claim(NOW), parse(detail, "detail", movie_path), NOW)
        config = Config(
            {"filmo.to": "https://filmo.to"},
            {"tv": "off", "movie": "off"},
            state_dir,
            output_dir,
            tmp_path / "unused-key",
            "synthetic-filmo",
            "127.0.0.1",
            8080,
            {key: value[0] for key, value in LIMITS.items()},
        )
        publish(config, state, NOW)
    finally:
        state.close()
    return output_dir


def _published_filmo_audio(tmp_path: Path) -> Path:
    state_dir, output_dir = tmp_path / "audio-state", tmp_path / "audio-published"
    state = State(state_dir / "filmo.to.sqlite", "filmo.to")
    movie_path = "/movies/audio-example"
    chips = (
        ("42", "VOE", "English Dub German Sub", "BluRay", "720p"),
        ("84", "Byse", "Japanese Dub", "WEB", "1080p"),
        ("99", "VOE", "Unknown", "WEB", "480p"),
    )
    detail = (
        "<!doctype html><html><body><h1>Audio Film</h1>"
        + "".join(
            f'<div class="provider-row"><span class="provider-row__lang">{label}</span>'
            f'<div data-provider-chip aria-label="{host}" data-movie-link-id="{native_id}" '
            f'data-p="fixture-{native_id}"><span class="provider-chip__metadata-tag">{source}</span>'
            f'<span class="provider-chip__metadata-tag">{resolution}</span></div></div>'
            for native_id, host, label, source, resolution in chips
        )
        + "</body></html>"
    ).encode()
    listing = b'<!doctype html><html><body><div class="movie-poster-grid-card"><a href="/movies/audio-example">Audio Film</a></div></body></html>'
    state.listing(parse(listing, "listing", "/movies"), NOW)
    try:
        state.detail(state.claim(NOW), parse(detail, "detail", movie_path), NOW)
        config = Config(
            {"filmo.to": "https://filmo.to"},
            {"tv": "off", "movie": "off"},
            state_dir,
            output_dir,
            tmp_path / "unused-key",
            "synthetic-filmo",
            "127.0.0.1",
            8080,
            {key: value[0] for key, value in LIMITS.items()},
        )
        publish(config, state, NOW)
    finally:
        state.close()
    return output_dir


def _job_store(tmp_path: Path) -> Jobs:
    database = tmp_path / "local-jobs.sqlite"
    with closing(sqlite3.connect(database)) as db, db:
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
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    return Jobs(database, downloads, {"filmo.to"})


def test_filmo_variants_flow_through_publication_search_rss_and_durable_jobs(tmp_path):
    published = _published_filmo(tmp_path)
    app = create_app(published, TOKEN, now=NOW)
    client = Client(
        "http://127.0.0.1",
        "synthetic-filmo",
        TOKEN,
        Cache(tmp_path / "query-cache.sqlite"),
        transport=httpx.ASGITransport(app=app),
    )
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    search = Search(client, tmp_path / "local-jobs.sqlite", scratch, "filmo.to")
    jobs = _job_store(tmp_path)

    async def fetch_rows():
        rows, total, _ = await search.search(
            {"t": "movie", "q": "Example Film"}, now=NOW
        )
        await client.close()
        return rows, total

    rows, total = asyncio.run(fetch_rows())
    assert total == 2 and len(rows) == 2
    assert {row["release_metadata"]["native_id"] for row in rows} == {"42", "84"}
    assert {row["release_metadata"]["host"] for row in rows} == {"VOE", "Byse"}

    root = ET.fromstring(rss(rows, total, 0, seeders=2, leechers=1))
    items = root.findall("./channel/item")
    assert len(items) == 2
    magnets = [item.findtext("link") for item in items]
    assert all(value and value.startswith("magnet:?xt=") for value in magnets)
    decoded = [magnet.decode(value) for value in magnets]
    assert decoded[0][0] != decoded[1][0]
    assert {item[1]["release_metadata"]["native_id"] for item in decoded} == {
        "42",
        "84",
    }
    assert all(
        item[1]["release_metadata"]["audio_languages"] == ["eng"] for item in decoded
    )
    assert all(
        item[1]["release_metadata"]["subtitle_languages"] == ["deu"] for item in decoded
    )

    first, second = magnets
    first_job = jobs.admit(first, NOW, paused=True)[0]
    assert jobs.admit(first, NOW + 1) == [first_job]
    second_job = jobs.admit(second, NOW + 1, paused=True)[0]
    assert first_job != second_job
    with closing(jobs.db()) as db:
        frozen = {
            row["job_id"]: json.loads(row["payload"])
            for row in db.execute("SELECT job_id,payload FROM durable_request")
        }
    assert {
        payload["release_metadata"]["native_id"] for payload in frozen.values()
    } == {"42", "84"}
    assert len(frozen) == 2

    restarted = Jobs(jobs.filename, jobs.download_dir, {"filmo.to"})
    restarted.recover(NOW + 60, startup=True)
    assert restarted.get(first_job)["status"] == "paused"
    assert json.loads(restarted.get(first_job)["payload"]) == frozen[first_job]
    assert restarted.get(first_job)["attempts"] == 0
    restarted.action(first_job, "resume", NOW + 61)
    claim = restarted.claim(NOW + 62)
    assert claim["job_id"] == first_job
    assert restarted.get(first_job)["attempts"] == 1
    assert restarted.finish(first_job, claim["generation"], "challenge", NOW + 63)
    restarted = Jobs(jobs.filename, jobs.download_dir, {"filmo.to"})
    restarted.recover(NOW + 90, startup=True)
    assert restarted.get(first_job)["status"] == "blocked"
    assert restarted.get(first_job)["attempts"] == 1
    assert json.loads(restarted.get(first_job)["payload"]) == frozen[first_job]
    assert restarted.claim(NOW + 91) is None
    restarted.action(first_job, "retry", NOW + 120)
    assert restarted.get(first_job)["attempts"] == 0
    assert json.loads(restarted.get(first_job)["payload"]) == frozen[first_job]


def test_filmo_torznab_filters_unknown_audio_before_pagination(tmp_path):
    output = _published_filmo_audio(tmp_path)
    published = output / "filmo.to"
    manifest = json.loads((published / "current.json").read_text())
    with closing(schema.connect(published / manifest["database"])) as db:
        assert "und" in {row[0] for row in db.execute("SELECT language FROM release")}

    app = create_app(output, TOKEN, now=NOW)
    client = Client(
        "http://127.0.0.1",
        "synthetic-filmo",
        TOKEN,
        Cache(tmp_path / "audio-cache.sqlite"),
        transport=httpx.ASGITransport(app=app),
    )
    scratch = tmp_path / "audio-scratch"
    scratch.mkdir()
    jobs = _job_store(tmp_path)
    search = Search(client, jobs.filename, scratch, "filmo.to")

    async def run():
        first, first_total, _ = await search.search(
            {"t": "movie", "limit": "1", "offset": "0"}, now=NOW
        )
        second, second_total, _ = await search.search(
            {"t": "movie", "limit": "1", "offset": "1"}, now=NOW
        )
        assert first_total == second_total == 2
        assert len(first) == len(second) == 1
        assert first[0]["release_id"] != second[0]["release_id"]

        all_known, known_total, _ = await search.search(
            {"t": "movie", "q": "Audio Film"}, now=NOW
        )
        assert known_total == 2 and len(all_known) == 2
        english = next(
            row for row in all_known if row["release_metadata"]["native_id"] == "42"
        )
        assert english["release_metadata"]["audio_languages"] == ["eng"]
        assert english["release_metadata"]["subtitle_languages"] == ["deu"]

        japanese, japanese_total, _ = await search.search(
            {"t": "movie", "q": "Audio Film"},
            now=NOW,
            languages={"filmo.to": {"jpn"}},
        )
        assert japanese_total == 1 and len(japanese) == 1
        assert japanese[0]["release_metadata"]["native_id"] == "84"

        request_count = client.requests
        empty, empty_total, _ = await search.search(
            {"t": "movie"}, now=NOW, languages={"filmo.to": set()}
        )
        assert empty == [] and empty_total == 0
        assert client.requests == request_count
        await client.close()

    asyncio.run(run())
