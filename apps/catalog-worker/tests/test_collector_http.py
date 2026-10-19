"""Local HTTP collection fixtures; outbound transport policy is tested separately."""

import asyncio
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from catalog_worker.collector import Collector
from catalog_worker.config import LIMITS, Config
from catalog_worker.state import State
from catalog_worker.transport import Fetch, challenge

pytestmark = pytest.mark.skipif(
    sys.platform != "linux",
    reason="private parser runtime requires Linux enforcement; native gate remains open",
)
NOW = 1800000000
TITLE = "/anime/stream/example"


@pytest.mark.parametrize("provider", ["aniworld.to", "s.to", "megakino"])
def test_http_paging_failure_and_resume(tmp_path, provider):
    pages = {
        "/animes-alphabet": (
            200,
            '<a href="/anime/stream/example">Example</a><a rel="next" href="/animes-alphabet/2">Next</a>',
        ),
        "/animes-alphabet/2": (200, '<a href="/anime/stream/second">Second</a>'),
        TITLE: (200, f'<h1>Example</h1><a href="{TITLE}/staffel-1">Season</a>'),
        TITLE + "/staffel-1": (200, f'<a href="{TITLE}/staffel-1/episode-1">First</a>'),
        TITLE + "/staffel-1/episode-1": (
            200,
            '<h1>Example</h1><small class="episodeEnglishTitle">First</small><li data-lang-key="1" data-link-target="/redirect/private"></li>',
        ),
    }
    if provider == "s.to":

        def convert(value):
            return (
                value.replace("/anime/stream/", "/serie/")
                .replace("/animes-alphabet/2", "/serien?by=alpha&amp;page=2")
                .replace("/animes-alphabet", "/serien?by=alpha")
            )

        pages = {
            convert(path).replace("&amp;", "&"): (
                status,
                convert(body).replace(
                    '<li data-lang-key="1" data-link-target="/redirect/private"></li>',
                    '<button data-play-url="/r/private" data-provider-name="VOE" data-language-label="Deutsch"></button>',
                ),
            )
            for path, (status, body) in pages.items()
        }
    if provider == "megakino":
        ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
        pages = {
            "/sitemap.xml": (
                200,
                f'<sitemapindex xmlns="{ns}"><sitemap><loc>/sitemap1.xml</loc></sitemap></sitemapindex>',
            ),
            "/sitemap1.xml": (
                200,
                f'<urlset xmlns="{ns}"><url><loc>/films/123-example.html</loc></url><url><loc>/films/124-another.html</loc></url></urlset>',
            ),
            "/films/123-example.html": (
                200,
                '<h1>Example</h1><iframe src="https://host.invalid/private" data-language-label="Deutsch"></iframe>',
            ),
            "/films/124-another.html": (
                200,
                '<h1>Another</h1><iframe src="https://host.invalid/private" data-language-label="Deutsch"></iframe>',
            ),
        }
    if provider in ("aniworld.to", "s.to"):
        pages["/neue-episoden"] = (
            200,
            '<div class="newEpisodeList"></div>'
            if provider == "aniworld.to"
            else '<table class="new-episodes-table"></table>',
        )
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            status, body = pages.get(self.path, (404, "not found"))
            self.send_response(status)
            self.end_headers()
            if provider == "megakino" and self.path.endswith(".xml"):
                self.wfile.write(body.encode())
                return
            self.wfile.write(
                (
                    "<html><body><div class=hosterSiteVideo>"
                    + body
                    + "</div></body></html>"
                ).encode()
            )

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    limits = {key: bounds[0] for key, bounds in LIMITS.items()}
    config = Config(
        {provider: origin},
        {"tv": "off"},
        tmp_path,
        tmp_path / "output",
        tmp_path / "key",
        "fixture",
        "127.0.0.1",
        1,
        limits,
    )
    now = NOW

    async def local_fixture_fetch(origin, path, **kwargs):
        # Test-only HTTP origin: production fetch correctly disallows loopback.
        await kwargs["before_request"]()
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(
                origin + path, params=kwargs.get("query"), timeout=kwargs["deadline"]
            )
        assert len(response.content) <= kwargs["body_bytes"]
        outcome = {
            404: "not_found",
            429: "rate_limited",
            403: "challenge_or_block",
        }.get(response.status_code, "ok")
        if challenge(response.content):
            outcome = "challenge_or_block"
        return Fetch(
            outcome, response.content, 3600 if response.status_code == 429 else None
        )

    state = State(tmp_path / "worker.sqlite", provider)

    def tick():
        nonlocal now
        now += 3
        return asyncio.run(
            Collector(
                config, state, fetcher=local_fixture_fetch, clock=lambda: now
            ).tick()
        )

    try:
        assert tick()
        assert state.meta()["listing_checked_at"] == 0
        state.close()
        state = State(tmp_path / "worker.sqlite", provider)
        assert tick()
        assert state.db.execute("SELECT count(*) FROM title").fetchone()[0] == 2
        assert calls[:2] == list(pages)[:2]
        for _ in range(8):
            tick()
        row = state.db.execute("SELECT * FROM release").fetchone()
        assert row and row["language"] == "de-dub"
        first_seen = row["first_seen_at"]
        work = dict(
            state.db.execute(
                "SELECT * FROM work WHERE kind=? ORDER BY path",
                ("title" if provider == "megakino" else "episode",),
            ).fetchone()
        )
        pages[work["path"]] = (200, "cf-turnstile captcha-form")
        with state.db:
            state.db.execute(
                "UPDATE work SET due=0,checked_at=? WHERE path=?",
                (now - 604801, work["path"]),
            )
        tick()
        assert state.meta()["state"] == "blocked"
        count = len(calls)
        assert not tick() and len(calls) == count
        assert (
            state.db.execute(
                "SELECT first_seen_at FROM release WHERE release_id=?",
                (row["release_id"],),
            ).fetchone()[0]
            == first_seen
        )
    finally:
        state.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
