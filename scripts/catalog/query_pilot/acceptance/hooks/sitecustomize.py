"""Test-only I/O fixture, loaded solely by acceptance.yaml's PYTHONPATH.

Never install this in production. It supplies fixed provider/player HTML and
generated MP4 bytes; DNS/TLS for those URLs are simulated. It does not replace
resolve(), transfer(), SubprocessExecutor, job children, outcomes or DB writes.
"""

import json
import os
import sys
from pathlib import Path
from collections.abc import Iterator
from urllib.parse import urlsplit

import httpx

from app.core.downloader import provider_policy

MEDIA = Path("/generated/generated.mp4")
EPISODE = "/anime/stream/generated-client-fixture/staffel-1/episode-1"
URLS = {
    "https://fixture.invalid" + EPISODE: "provider",
    "https://fixture.invalid/player": "player",
    "https://media.fixture.invalid/generated.mp4": "media",
}
ADDRESS = "192.0.2.77"  # Never contacted: fixture transport handles these requests.
real_validate = provider_policy._validate_request_url
real_client = httpx.Client


def validate(url: str, **kwargs: object) -> tuple[str, int, str]:
    if url in URLS:
        if not MEDIA.is_file():
            raise ValueError("generated input is missing")
        host = urlsplit(url).hostname
        assert host is not None
        return host, 443, ADDRESS
    if urlsplit(url).hostname in {"fixture.invalid", "media.fixture.invalid"}:
        raise ValueError("outside the single generated acceptance episode")
    return real_validate(url, **kwargs)


def event(stage: str) -> None:
    # Short records, no query, address, token or signed URL logging.
    path = Path("/data/acceptance-http-events.jsonl")
    with path.open("a") as stream:
        stream.write(
            json.dumps(
                {"pid": os.getpid(), "process": Path(sys.argv[0]).name, "input": stage}
            )
            + "\n"
        )


class Body(httpx.SyncByteStream):
    def __iter__(self) -> Iterator[bytes]:
        with MEDIA.open("rb") as stream:
            while block := stream.read(65536):
                yield block


class Transport(httpx.BaseTransport):
    def __init__(self, fallback: httpx.BaseTransport) -> None:
        self.fallback = fallback

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != ADDRESS:
            return self.fallback.handle_request(request)
        host = request.headers.get("Host")
        logical = "https://" + str(host) + request.url.path
        stage = URLS.get(logical)
        if stage is None or request.method != "GET" or request.url.query:
            raise ValueError("undeclared generated request")
        event(stage)
        if stage == "provider":
            html = (
                "<html><body>"
                + "".join(
                    f'<li data-lang-key="{key}" data-link-target="/player"><h4>Vidoza</h4><a href="/player">generated</a></li>'
                    for key in ("1", "2")
                )
                + "</body></html>"
            )
            return httpx.Response(200, stream=httpx.ByteStream(html.encode()))
        if stage == "player":
            return httpx.Response(
                200,
                stream=httpx.ByteStream(
                    b'sourcesCode: [{src: "https://media.fixture.invalid/generated.mp4"}]'
                ),
            )
        return httpx.Response(
            200,
            headers={
                "Content-Length": str(MEDIA.stat().st_size),
                "Content-Type": "video/mp4",
            },
            stream=Body(),
        )

    def close(self) -> None:
        self.fallback.close()


class Client(real_client):
    def __init__(self, *args: object, **kwargs: object) -> None:
        if "transport" not in kwargs:
            kwargs["transport"] = Transport(httpx.HTTPTransport(trust_env=False))
        super().__init__(*args, **kwargs)


provider_policy._validate_request_url = validate
httpx.Client = Client
