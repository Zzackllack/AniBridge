import httpx
import pytest

from app.catalog.aniworld_resolution import resolve
from app.catalog.resolution_transport import Budget, ResolutionError


class Body(httpx.SyncByteStream):
    def __init__(self, value):
        self.value, self.closed = value, False

    def __iter__(self):
        yield self.value

    def close(self):
        self.closed = True


def transport(pages, **kwargs):
    calls, bodies, validated = [], [], []

    def request(request):
        calls.append(request)
        status, headers, value = pages[request.url.path]
        body = Body(value)
        bodies.append(body)
        return httpx.Response(status, headers=headers, stream=body)

    def validate(url, *, stage):
        validated.append(url)
        target = httpx.URL(url)
        if target.scheme != "https" or target.host in ("127.0.0.1", "localhost"):
            raise ValueError("unsafe")
        return target.host, 443, "8.8.8.8"

    budget = Budget(
        client=httpx.Client(transport=httpx.MockTransport(request)),
        validate_url=validate,
        **kwargs,
    )
    return budget, calls, bodies, validated


def test_resolution_pins_each_hop_and_keeps_tokens_out_of_repr():
    pages = {
        "/anime/stream/example/staffel-1/episode-1": (
            200,
            {},
            b'<li data-lang-key="1" data-link-target="redirect"><a href="/redirect/one"><h4>VOE</h4></a></li>',
        ),
        "/redirect/one": (302, {"location": "https://host.example/e/one"}, b""),
        "/e/one": (200, {}, b"synthetic encoded source"),
    }
    budget, calls, bodies, validated = transport(pages)
    try:
        result = resolve(
            {
                "provider": "aniworld.to",
                "path": next(iter(pages)),
                "language": "de-dub",
            },
            "https://aniworld.example",
            ("VOE",),
            budget,
            source_parser=lambda html: "https://media.example/video.m3u8?token=private",
            redirect_parser=lambda html, url: None,
        )
        assert result.host == "VOE" and result.url.endswith("token=private")
        assert "private" not in repr(result)
        assert len(calls) == 3 and budget.requests_left == 13
        assert calls[0].url.host == "8.8.8.8"
        assert calls[0].headers["Host"] == "aniworld.example"
        assert calls[-1].extensions["sni_hostname"] == "host.example"
        assert validated[-1] == result.url
        assert all(body.closed for body in bodies)
    finally:
        budget.close()


@pytest.mark.parametrize(
    "status,body,code",
    [
        (200, b"cf-turnstile captcha-form", "challenge"),
        (403, b"", "challenge"),
        (404, b"", "unavailable"),
        (429, b"", "transport_failure"),
        (200, b"x" * 100, "extraction_error"),
    ],
)
def test_failures_are_typed_and_responses_close(status, body, code):
    budget, _, bodies, _ = transport({"/page": (status, {}, body)}, body_bytes=64)
    try:
        with pytest.raises(ResolutionError, match=code):
            budget.get("https://example.test/page")
        assert all(body.closed for body in bodies)
    finally:
        budget.close()


def test_request_bytes_and_deadline_are_shared_across_calls():
    clock = [1.0]
    budget, calls, bodies, _ = transport(
        {"/page": (200, {}, b"1234")}, body_bytes=6, clock=lambda: clock[0]
    )
    try:
        budget.get("https://example.test/page")
        with pytest.raises(ResolutionError, match="extraction_error"):
            budget.get("https://example.test/page")
        assert len(calls) == 2 and all(body.closed for body in bodies)
        clock[0] = 100
        with pytest.raises(ResolutionError, match="transport_failure"):
            budget.get("https://example.test/page")
        assert len(calls) == 2
    finally:
        budget.close()
    budget, calls, _, _ = transport(
        {"/page": (302, {"location": "/again"}, b"")}, requests=1
    )
    try:
        with pytest.raises(ResolutionError, match="extraction_error"):
            budget.get("https://example.test/page")
        assert len(calls) == 1
    finally:
        budget.close()


def test_private_redirect_and_cross_origin_provider_are_rejected_before_request():
    budget, calls, _, _ = transport(
        {"/page": (302, {"location": "https://127.0.0.1/private"}, b"")}
    )
    try:
        with pytest.raises(ResolutionError, match="extraction_error"):
            budget.get("https://example.test/page")
        assert len(calls) == 1
        with pytest.raises(ResolutionError, match="extraction_error"):
            budget.get("https://unrelated.test/page", origin="https://provider.test")
        assert len(calls) == 1
    finally:
        budget.close()


def test_prefix_range_is_bounded_even_when_server_ignores_it():
    budget, calls, bodies, _ = transport(
        {"/media": (200, {}, b"x" * 1000)}, body_bytes=100
    )
    try:
        assert budget.prefix("https://media.example/media", 100) == b"x" * 100
        assert calls[0].headers["range"] == "bytes=0-99"
        assert budget.bytes_left == 0 and bodies[0].closed
        with pytest.raises(ResolutionError):
            budget.prefix("https://media.example/media", 1)
        assert len(calls) == 1
    finally:
        budget.close()


def test_sto_uses_explicit_audio_label_and_same_attempt_budget():
    pages = {
        "/serie/example/staffel-0/episode-1": (
            200,
            {},
            b'<button data-play-url="/r/english" data-provider-name="VOE" data-language-label="Englisch" data-language-id="2"></button><button data-play-url="/r/german" data-provider-name="VOE" data-language-label="Deutsch"></button>',
        ),
        "/r/english": (200, {}, b"source"),
    }
    budget, calls, _, _ = transport(pages)
    try:
        result = resolve(
            {"provider": "s.to", "path": next(iter(pages)), "language": "en-dub"},
            "https://sto.example",
            ("VOE",),
            budget,
            source_parser=lambda _: "https://media.example/file",
            redirect_parser=lambda *_: None,
        )
        assert result.host == "VOE" and [r.url.path for r in calls] == list(pages)
        with pytest.raises(ResolutionError, match="unavailable"):
            resolve(
                {"provider": "s.to", "path": next(iter(pages)), "language": "en-sub"},
                "https://sto.example",
                ("VOE",),
                budget,
                source_parser=lambda _: None,
                redirect_parser=lambda *_: None,
            )
        assert len(calls) == 3  # no language fallback or second host request
    finally:
        budget.close()


def test_megakino_selects_labelled_player_without_assuming_original_language():
    pages = {
        "/films/123-example.html": (
            200,
            {},
            b'<script type="application/ld+json">{"@type":"Movie","inLanguage":"de"}</script><iframe src="https://voe.sx/e/one"></iframe>',
        ),
        "/e/one": (200, {}, b"source"),
    }
    budget, calls, _, _ = transport(pages)
    payload = {
        "provider": "megakino",
        "kind": "movie",
        "path": next(iter(pages)),
        "language": "de-dub",
    }
    try:
        with pytest.raises(ResolutionError, match="unavailable"):
            resolve(payload, "https://movie.example", ("VOE",), budget)
        assert len(calls) == 1
        pages[payload["path"]] = (
            200,
            {},
            b'<iframe src="https://voe.sx/e/one" data-language-label="Deutsch"></iframe>',
        )
        result = resolve(
            payload,
            "https://movie.example",
            ("VOE",),
            budget,
            source_parser=lambda _: "https://media.example/file",
            redirect_parser=lambda *_: None,
        )
        assert result.host == "VOE" and len(calls) == 3
        assert calls[-1].headers["Host"] == "voe.sx"
        with pytest.raises(ResolutionError, match="extraction_error"):
            resolve(
                {**payload, "path": "/serials/123-example.html"},
                "https://movie.example",
                ("VOE",),
                budget,
            )
        assert len(calls) == 3
    finally:
        budget.close()


@pytest.mark.parametrize(
    "host,player",
    [
        (
            "Filemoon",
            b'<script>sources: [{file: "https://media.example/generated.m3u8?token=fixture"}]</script>',
        ),
        (
            "Vidoza",
            b'<script>sourcesCode: [{src: "https://media.example/generated.mp4?token=fixture"}]</script>',
        ),
    ],
)
def test_installed_pure_host_parsers_share_bounded_transport(host, player):
    pages = {
        "/anime/stream/example/staffel-1/episode-1": (
            200,
            {},
            f'<li data-lang-key="1" data-link-target="r"><a href="/r/host"><h4>{host}</h4></a></li>'.encode(),
        ),
        "/r/host": (200, {}, player),
    }
    budget, calls, bodies, validated = transport(pages)
    try:
        result = resolve(
            {
                "provider": "aniworld.to",
                "path": next(iter(pages)),
                "language": "de-dub",
            },
            "https://provider.example",
            (host,),
            budget,
        )
        assert result.host == host and "generated" in result.url
        assert validated[-1] == result.url
        assert len(calls) == 2 and all(body.closed for body in bodies)
        assert "fixture" not in repr(result)
    finally:
        budget.close()


def test_filemoon_encrypted_api_is_observed_same_origin_and_quality_unasserted():
    import base64
    import json
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key, iv = bytes(range(32)), bytes(range(12))

    def encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    plaintext = json.dumps(
        {
            "sources": [
                {"url": "https://media.example/low.mp4", "height": 360},
                {"url": "https://media.example/high.m3u8", "height": 720},
            ]
        }
    ).encode()
    playback = {
        "key_parts": [encode(key[:16]), encode(key[16:])],
        "iv": encode(iv),
        "payload": encode(AESGCM(key).encrypt(iv, plaintext, None)),
    }
    pages = {
        "/serie/example/staffel-1/episode-1": (
            200,
            {},
            b'<button data-play-url="https://host.example/e/abc123" data-provider-name="Filemoon" data-language-label="Deutsch"></button>',
        ),
        "/e/abc123": (200, {}, b"<script>generated encrypted API player</script>"),
        "/api/videos/abc123": (200, {}, json.dumps({"playback": playback}).encode()),
    }
    budget, calls, bodies, validated = transport(pages)
    try:
        result = resolve(
            {"provider": "s.to", "path": next(iter(pages)), "language": "de-dub"},
            "https://provider.example",
            ("Filemoon",),
            budget,
        )
        assert result.url == "https://media.example/high.m3u8"
        assert not hasattr(result, "height") and not hasattr(result, "codec")
        assert calls[-1].headers["Host"] == "host.example" and len(calls) == 3
        assert validated[-1] == result.url and all(body.closed for body in bodies)
        # Hostile decrypted URLs still pass through the same SSRF validation.
        playback["payload"] = encode(
            AESGCM(key).encrypt(
                iv,
                b'{"source":"https://127.0.0.1/private"}',
                None,
            )
        )
        pages["/api/videos/abc123"] = (
            200,
            {},
            json.dumps({"playback": playback}).encode(),
        )
        with pytest.raises(ResolutionError, match="extraction_error"):
            resolve(
                {"provider": "s.to", "path": next(iter(pages)), "language": "de-dub"},
                "https://provider.example",
                ("Filemoon",),
                budget,
            )
        assert not any(call.url.path == "/private" for call in calls)
    finally:
        budget.close()


def test_unsupported_hosts_do_not_consume_a_supported_offer_or_run_legacy_network():
    pages = {
        "/anime/stream/example/staffel-1/episode-1": (
            200,
            {},
            b'<li data-lang-key="1" data-link-target="r"><a href="/r/unsupported"><h4>Streamtape</h4></a></li><li data-lang-key="1" data-link-target="r"><a href="/r/source"><h4>Vidoza</h4></a></li>',
        ),
        "/r/source": (
            200,
            {},
            b'sourcesCode: [{src:"https://media.example/generated.mp4"}]',
        ),
    }
    budget, calls, _, _ = transport(pages)
    try:
        result = resolve(
            {
                "provider": "aniworld.to",
                "path": next(iter(pages)),
                "language": "de-dub",
            },
            "https://provider.example",
            ("Streamtape", "Vidoza"),
            budget,
        )
        assert result.host == "Vidoza"
        assert not any(call.url.path == "/r/unsupported" for call in calls)
    finally:
        budget.close()


def test_installed_host_parsers_run_in_real_memory_bounded_child(tmp_path):
    import os
    import subprocess
    import sys
    import textwrap

    if sys.platform != "linux":
        pytest.skip("hard child memory enforcement is Linux-only")
    script = textwrap.dedent("""
        from catalog_core.supervisor import limit_child
        limit_child()
        import resource
        assert resource.getrlimit(resource.RLIMIT_AS) == (256 * 1024**2,) * 2
        from app.hosts.catalog_sources import html_source
        assert html_source('Filemoon', 'sources:[{file:"https://media.invalid/generated.m3u8"}]') == 'https://media.invalid/generated.m3u8'
        assert html_source('Vidoza', 'sourcesCode:[{src:"https://media.invalid/generated.mp4"}]') == 'https://media.invalid/generated.mp4'
        print('INSTALLED_HOST_PARSERS_WITHIN_CHILD_LIMIT')
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={
            **os.environ,
            "MALLOC_ARENA_MAX": "1",
            "ANIWORLD_INSTALL_FOLDER": str(tmp_path / "upstream"),
            "ANIBRIDGE_SUPERVISOR_PID": str(os.getpid()),
        },
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr[-1000:]
    assert "INSTALLED_HOST_PARSERS_WITHIN_CHILD_LIMIT" in result.stdout


@pytest.mark.parametrize(
    "playback",
    [
        {"key_parts": ["fixture"], "iv": 123, "payload": "fixture"},
        {"key_parts": ["fixture"] * 100},
        {"key_parts": [None]},
        {"key_parts": ["x" * 1024]},
    ],
)
def test_malformed_filemoon_playback_is_unresolved(playback):
    import json
    from app.hosts.catalog_sources import filemoon_source

    assert filemoon_source(json.dumps({"playback": playback})) is None


def test_megakino_bootstrap_uses_logical_cookie_and_one_retry():
    path = "/films/1-fixture.html"
    stub = (
        '<!doctype html><meta charset="utf-8"><script>'
        'fetch("/index.php?yg=token",{credentials:"include"})'
        '.then(function(){ location.replace("' + path + '") })'
        ".catch(function(){ location.reload() });</script>"
    ).encode()
    wire = []

    def reply(request):
        wire.append(request)
        if len(wire) == 1:
            return httpx.Response(200, stream=Body(stub))
        if len(wire) == 2:
            return httpx.Response(
                204,
                headers={"Set-Cookie": "session=generated; Path=/; Secure; HttpOnly"},
                stream=Body(b""),
            )
        return httpx.Response(200, stream=Body(b"<html>metadata</html>"))

    budget = Budget(
        client=httpx.Client(transport=httpx.MockTransport(reply)),
        validate_url=lambda url, **kwargs: ("movie.example", 443, "93.184.216.34"),
    )
    try:
        page = budget.get_megakino(
            "https://movie.example" + path, origin="https://movie.example"
        )
        assert page.text == "<html>metadata</html>" and budget.requests_left == 13
        assert wire[2].headers["cookie"] == "session=generated"
        assert all(
            r.url.host == "93.184.216.34"
            and r.extensions["sni_hostname"] == "movie.example"
            for r in wire
        )
        assert "cookie" not in wire[0].headers and "cookie" not in wire[1].headers
        budget.get("https://video.example/embed")
        assert "cookie" not in wire[3].headers
    finally:
        budget.close()
