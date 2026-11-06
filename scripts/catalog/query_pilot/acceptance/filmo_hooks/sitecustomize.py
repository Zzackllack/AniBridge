"""Test-only closed Filmo/Byse inputs for the disposable acceptance overlay.

This module is intentionally installed only by the acceptance overlay. It
patches the outbound transport boundary; production resolution, jobs, transfer,
progress, and client behavior continue to run normally.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from app.core.downloader import provider_policy

# httpx's INFO request records include full URLs. This test-only hook records
# only its finite input class below, so keep those lower-level records quiet.
logging.getLogger("httpx").setLevel(logging.WARNING)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import filmo_fixture  # noqa: E402

MEDIA = Path("/generated/generated.mp4")
ADDRESS = "192.0.2.77"  # The transport below handles this reserved address.
# The generated input takes about 98 seconds, spanning Radarr's minute poll.
CHUNK_DELAY_S = 0.25
EVENTS = Path("/data/filmo-acceptance-http-events.jsonl")
VARIANT_CHOICES: list[str] = []  # Test assertion only; never written to logs.

ROUTES = {
    ("fixture.invalid", "GET", "/movies"): "listing",
    ("fixture.invalid", "GET", filmo_fixture.MOVIE_PATH): "detail",
    ("fixture.invalid", "POST", "/n"): "mint",
    ("fixture.invalid", "GET", "/n/fixture-wrapper-primary"): "wrapper_primary",
    ("fixture.invalid", "GET", "/n/fixture-wrapper-alternate"): "wrapper_alternate",
    ("bysefixture.test", "GET", "/d/Abc123"): "byse_embed_primary",
    ("bysefixture.test", "GET", "/d/Def456"): "byse_embed_alternate",
    ("bysefixture.test", "GET", "/api/videos/Abc123"): "byse_api",
    ("bysefixture.test", "GET", "/api/videos/Def456"): "byse_api",
    ("media.fixture.invalid", "GET", "/generated.mp4"): "media",
}
URLS = {
    f"https://{host}{path}": stage for (host, _method, path), stage in ROUTES.items()
}
BLOCKED_HOSTS = {"fixture.invalid", "bysefixture.test", "media.fixture.invalid"}
real_validate = provider_policy._validate_request_url
real_client = httpx.Client


def validate(url: str, **kwargs: object) -> tuple[str, int, str]:
    parsed = urlsplit(url)
    if url in URLS:
        if not MEDIA.is_file():
            raise ValueError("generated Filmo media is missing")
        return parsed.hostname or "", 443, ADDRESS
    if parsed.hostname in BLOCKED_HOSTS:
        raise ValueError("outside the fixed generated Filmo inputs")
    return real_validate(url, **kwargs)


def event(stage: str) -> None:
    """Record only a closed route class; never write URLs, tokens, or query data."""
    if stage not in set(ROUTES.values()):
        raise ValueError("undeclared generated event")
    try:
        with EVENTS.open("a") as stream:
            stream.write(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "process": Path(sys.argv[0]).name,
                        "input": stage,
                    }
                )
                + "\n"
            )
    except OSError:
        # Some offline unit tests intentionally use an unmounted /data path.
        pass


class Body(httpx.SyncByteStream):
    def __init__(self, *, start: int = 0, length: int | None = None) -> None:
        self.start, self.length = start, length

    def __iter__(self) -> Iterator[bytes]:
        with MEDIA.open("rb") as stream:
            stream.seek(self.start)
            remaining = self.length
            while remaining is None or remaining > 0:
                block = stream.read(
                    65536 if remaining is None else min(65536, remaining)
                )
                if not block:
                    break
                if CHUNK_DELAY_S:
                    time.sleep(CHUNK_DELAY_S)
                if remaining is not None:
                    remaining -= len(block)
                yield block


class Transport(httpx.BaseTransport):
    def __init__(self, fallback: httpx.BaseTransport) -> None:
        self.fallback = fallback

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != ADDRESS:
            return self.fallback.handle_request(request)
        host = request.headers.get("Host", "").split(":", 1)[0].casefold()
        route = ROUTES.get((host, request.method, request.url.path))
        if route is None or request.url.query:
            raise ValueError("undeclared generated Filmo request")
        event(route)
        if route == "listing":
            return httpx.Response(
                200,
                stream=httpx.ByteStream(filmo_fixture.LISTING_HTML.encode()),
            )
        if route == "detail":
            return httpx.Response(
                200,
                headers={
                    "Set-Cookie": "session=fixture-session; Path=/; Secure; SameSite=Lax"
                },
                stream=httpx.ByteStream(filmo_fixture.DETAIL_HTML.encode()),
            )
        if route == "mint":
            if (
                request.headers.get("X-CSRF-TOKEN") != "fixture-csrf-v1"
                or request.headers.get("X-Requested-With") != "XMLHttpRequest"
                or "session=fixture-session" not in request.headers.get("Cookie", "")
            ):
                return httpx.Response(419, stream=httpx.ByteStream(b"{}"))
            try:
                payload = json.loads(request.content)
            except (UnicodeDecodeError, json.JSONDecodeError):
                return httpx.Response(400, stream=httpx.ByteStream(b"{}"))
            token = payload.get("p") if isinstance(payload, dict) else None
            wrappers = {
                "fixture-p-primary": ("primary", "fixture-wrapper-primary"),
                "fixture-p-alternate": ("alternate", "fixture-wrapper-alternate"),
            }
            selected = wrappers.get(token)
            if selected is None:
                return httpx.Response(404, stream=httpx.ByteStream(b"{}"))
            VARIANT_CHOICES.append(selected[0])
            return httpx.Response(
                200,
                headers={"Content-Type": "application/json"},
                stream=httpx.ByteStream(json.dumps({"x": selected[1]}).encode()),
            )
        if route in {"wrapper_primary", "wrapper_alternate"}:
            embed = (
                filmo_fixture.PRIMARY_EMBED
                if route == "wrapper_primary"
                else filmo_fixture.ALTERNATE_EMBED
            )
            body = f'<html><body><a href="{embed}">Continue</a></body></html>'
            return httpx.Response(200, stream=httpx.ByteStream(body.encode()))
        if route.startswith("byse_embed_"):
            # Deliberately no source URL: production must use its Byse decoder.
            return httpx.Response(
                200,
                stream=httpx.ByteStream(b"<html><body>Generated embed</body></html>"),
            )
        if route == "byse_api":
            return httpx.Response(
                200,
                headers={"Content-Type": "application/json"},
                stream=httpx.ByteStream(filmo_fixture.byse_response()),
            )

        range_header = request.headers.get("Range")
        if range_header:
            import re

            match = re.fullmatch(r"bytes=0-([0-9]{0,8})", range_header)
            if match is None:
                raise ValueError("unsupported generated media range")
            size = MEDIA.stat().st_size
            end = min(int(match[1]) if match[1] else size - 1, size - 1)
            length = end + 1
            return httpx.Response(
                206,
                headers={
                    "Content-Length": str(length),
                    "Content-Range": f"bytes 0-{end}/{size}",
                    "Content-Type": "video/mp4",
                },
                stream=Body(length=length),
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
