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
    budget, calls, _, _ = transport(
        {"/page": (302, {"location": "/again"}, b"")}, requests=1
    )
    try:
        with pytest.raises(ResolutionError, match="extraction_error"):
            budget.get("https://example.test/page")
        assert len(calls) == 1
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


def test_filmo_exchange_pins_same_origin_and_preserves_session_cookie():
    wire = []

    def reply(request):
        wire.append(request)
        return httpx.Response(419, stream=Body(b"expired CSRF"))

    budget = Budget(
        client=httpx.Client(transport=httpx.MockTransport(reply)),
        validate_url=lambda url, **kwargs: ("filmo.example", 443, "93.184.216.34"),
    )
    cookies = httpx.Cookies()
    cookies.set("session", "fixture", domain="filmo.example", path="/")
    try:
        response = budget.filmo_exchange(
            "POST",
            "https://filmo.example/n",
            origin="https://filmo.example",
            cookies=cookies,
            headers={"X-CSRF-TOKEN": "csrf-fixture"},
            json_body={"p": "opaque-fixture"},
        )
        assert response.status == 419 and "CSRF" in response.body.decode()
        assert wire[0].url.host == "93.184.216.34"
        assert wire[0].headers["host"] == "filmo.example"
        assert wire[0].headers["cookie"] == "session=fixture"
        assert wire[0].headers["x-csrf-token"] == "csrf-fixture"
        assert wire[0].read() == b'{"p":"opaque-fixture"}'
        assert "opaque-fixture" not in repr(response)
        with pytest.raises(ResolutionError, match="extraction_error"):
            budget.filmo_exchange(
                "POST",
                "https://evil.example/n",
                origin="https://filmo.example",
                cookies=cookies,
                json_body={"p": "x"},
            )
        assert len(wire) == 1
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


def test_byse_is_recognized_only_on_https_byse_embed_shapes():
    from app.hosts import detect_host
    from app.hosts.catalog_sources import byse_api

    accepted = "https://byseabc123.com/d/Abc123"
    assert detect_host(accepted).name == "Byse"
    assert byse_api(accepted) == "https://byseabc123.com/api/videos/Abc123"
    assert (
        byse_api("https://byseabc123.com/e/Abc123")
        == "https://byseabc123.com/api/videos/Abc123"
    )
    for rejected in (
        "http://byseabc123.com/d/Abc123",
        "https://notbyse.example/d/Abc123",
        "https://byseabc123.com.evil.test/d/Abc123",
        "https://byseabc123.com/d/Abc123?redirect=https://evil.test",
        "https://user@byseabc123.com/d/Abc123",
        "https://byseabc123.com/other/Abc123",
    ):
        assert byse_api(rejected) is None


@pytest.mark.parametrize("version", [1, "1", " 1 ", 20, "20"])
def test_bounded_byse_versioned_key_parts_decode_with_installed_pure_parser(version):
    import base64
    import json
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from app.hosts.catalog_sources import filemoon_source

    key, iv = bytes(range(32)), bytes(range(12))

    def encode(value):
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    plaintext = json.dumps(
        {"sources": [{"url": "https://media.example/video.m3u8", "height": 1080}]}
    ).encode()
    parts = [encode(bytes([index]) * 16) for index in range(30)]
    selected = int(version)
    parts[selected - 1], parts[30 - selected] = encode(key[:16]), encode(key[16:])
    playback = {
        "version": version,
        "algorithm": "AES-256-GCM",
        "key_parts": parts,
        "iv": encode(iv),
        "payload": encode(AESGCM(key).encrypt(iv, plaintext, None)),
    }
    assert len(playback["key_parts"]) == 30
    assert (
        filemoon_source(json.dumps({"playback": playback}))
        == "https://media.example/video.m3u8"
    )
    playback["key_parts"] *= 3
    assert filemoon_source(json.dumps({"playback": playback})) is None


def _encrypted_byse_response(data, *, api_tracks=None):
    import base64
    import json
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key, iv = bytes(range(32)), bytes(range(12))

    def encode(value):
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    parts = [encode(bytes([index]) * 16) for index in range(30)]
    parts[0], parts[29] = encode(key[:16]), encode(key[16:])
    plaintext = json.dumps(data, separators=(",", ":")).encode()
    playback = {
        "version": "1",
        "algorithm": "AES-256-GCM",
        "key_parts": parts,
        "iv": encode(iv),
        "payload": encode(AESGCM(key).encrypt(iv, plaintext, None)),
    }
    response = {"playback": playback}
    if api_tracks is not None:
        response["tracks"] = api_tracks
    return json.dumps(response)


def test_filmo_byse_captions_fail_resolution_and_legacy_decoder_is_unchanged(
    monkeypatch,
):
    from app.catalog import filmo_resolution
    from app.hosts.catalog_sources import filemoon_source

    media_url = "https://media.example/generated.mp4"
    response = _encrypted_byse_response(
        {
            "sources": [{"url": media_url, "height": 720}],
            "tracks": [
                {
                    "file": "https://captions.example/generated.vtt",
                    "kind": "captions",
                    "label": "German",
                }
            ],
        }
    )

    # Legacy Filemoon/Byse jobs retain their established URL-only decoding.
    assert filemoon_source(response) == media_url

    monkeypatch.setattr(
        filmo_resolution,
        "_filmo_embed",
        lambda *args, **kwargs: ("Byse", "https://bysefixture.test/d/Abc123"),
    )

    class FakeBudget:
        def __init__(self):
            self.urls = []

        def get(self, url, *, origin=None):
            self.urls.append(url)
            body = "<html></html>" if "/d/" in url else response
            return type("Page", (), {"url": url, "text": body})()

        def validate_url(self, url, *, stage):
            self.urls.append(url)
            return "media.example", 443, "8.8.8.8"

        def remaining(self):
            pass

    budget = FakeBudget()
    payload = {
        "provider": "filmo.to",
        "path": "/movies/example",
        "language": "eng",
        "variant_anchor": "frozen-variant",
        "release_metadata": {"variant_anchor": "frozen-variant"},
    }
    with pytest.raises(ResolutionError, match="unsupported_media_tracks") as error:
        resolve(payload, "https://filmo.example", ("Byse",), budget)
    assert error.value.code == "unsupported_media_tracks"
    assert not any(url == media_url for url in budget.urls)


def test_filmo_byse_track_layout_requires_explicit_thumbnail_only_metadata():
    from app.hosts.catalog_sources import (
        UnsupportedMediaTracks,
        filemoon_source,
    )

    media_url = "https://media.example/generated.mp4"
    response = _encrypted_byse_response(
        {
            "sources": [{"url": media_url, "height": 720}],
            "tracks": [
                {"file": "https://thumb.example/sprite.vtt", "kind": "thumbnails"}
            ],
        }
    )
    assert filemoon_source(response, reject_external_tracks=True) == media_url

    unknown = _encrypted_byse_response(
        {"sources": [{"url": media_url}], "tracks": {"subtitles": []}}
    )
    with pytest.raises(UnsupportedMediaTracks):
        filemoon_source(unknown, reject_external_tracks=True)

    api_captions = _encrypted_byse_response(
        {"sources": [{"url": media_url}]},
        api_tracks=[{"kind": "captions", "file": "https://captions.example/sub.vtt"}],
    )
    with pytest.raises(UnsupportedMediaTracks):
        filemoon_source(api_captions, reject_external_tracks=True)


@pytest.mark.parametrize("path", ["/movies/example", "/movies/caf%C3%A9"])
def test_filmo_419_refreshes_offer_and_keeps_selected_native_variant(path):
    import json
    from app.catalog.filmo_resolution import _filmo_embed
    from app.catalog.resolution_transport import Exchange
    from catalog_core.providers import filmo

    detail = b"""<meta name="csrf-token" content="csrf-one"><h1>Example</h1>
      <div class="provider-row"><span class="provider-row__lang">Deutsch</span>
      <div data-provider-chip aria-label="VOE" data-movie-link-id="42" data-p="opaque-choice">
      <span class="provider-chip__metadata-tag">BluRay</span><span class="provider-chip__metadata-tag">720p</span>
      </div></div>"""
    offer = filmo.parse(detail, "detail", path).offers[0]

    class FakeBudget:
        def __init__(self):
            self.calls = []
            self.responses = [
                ("GET", 200, detail, {}),
                ("POST", 419, b"", {}),
                ("GET", 200, detail.replace(b"csrf-one", b"csrf-two"), {}),
                ("POST", 200, json.dumps({"x": "wrap-secret"}).encode(), {}),
                ("GET", 302, b"", {"location": "https://voe.sx/e/selected"}),
            ]

        def filmo_exchange(self, method, url, **kwargs):
            expected_method, status, body, headers = self.responses.pop(0)
            assert method == expected_method
            self.calls.append((method, url, kwargs))
            if method == "POST":
                assert kwargs["json_body"]["p"] == "opaque-choice"
            return Exchange(url, status, httpx.Headers(headers), body)

    budget = FakeBudget()
    host, target = _filmo_embed(
        {"kind": "movie", "path": path},
        "https://filmo.to",
        budget,
        anchor=offer["variant_anchor"],
        metadata=offer,
    )
    assert (host, target) == ("VOE", "https://voe.sx/e/selected")
    assert len(budget.calls) == 5
    assert budget.calls[1][2]["headers"]["X-CSRF-TOKEN"] == "csrf-one"
    assert budget.calls[3][2]["headers"]["X-CSRF-TOKEN"] == "csrf-two"


def test_filmo_transport_keeps_canonical_encoded_slug_and_rejects_delimiters():
    wire = []

    def reply(request):
        wire.append(request)
        return httpx.Response(200, stream=Body(b"metadata"))

    budget = Budget(
        client=httpx.Client(transport=httpx.MockTransport(reply)),
        validate_url=lambda url, **kwargs: ("filmo.example", 443, "93.184.216.34"),
    )
    try:
        budget.filmo_exchange(
            "GET",
            "https://filmo.example/movies/caf%C3%A9",
            origin="https://filmo.example",
            cookies=httpx.Cookies(),
        )
        assert wire[0].url.raw_path == b"/movies/caf%C3%A9"
        for suffix in ("%2Fother", "%252Fother", "%2E%2E"):
            with pytest.raises(ValueError):
                budget.filmo_exchange(
                    "GET",
                    "https://filmo.example/movies/" + suffix,
                    origin="https://filmo.example",
                    cookies=httpx.Cookies(),
                )
        assert len(wire) == 1
    finally:
        budget.close()


def test_filmo_changed_quality_is_stale_and_is_not_replaced_by_another_offer():
    from app.catalog.filmo_resolution import _filmo_offer_token
    from app.catalog.resolution_transport import ResolutionError
    from catalog_core.providers import filmo

    original = b"""<h1>Example</h1><div class="provider-row"><span class="provider-row__lang">Deutsch</span>
      <div data-provider-chip aria-label="VOE" data-movie-link-id="42" data-p="opaque">
      <span class="provider-chip__metadata-tag">720p</span></div></div>"""
    changed = original.replace(b"720p", b"1080p")
    offer = filmo.parse(original, "detail", "/movies/example").offers[0]
    with pytest.raises(ResolutionError, match="stale_selection"):
        _filmo_offer_token(
            changed, {**offer, "path": "/movies/example"}, offer["variant_anchor"]
        )


def test_filmo_cosmetic_labels_do_not_permanently_stale_a_frozen_offer():
    from app.catalog.filmo_resolution import _filmo_offer_token
    from catalog_core.providers.filmo import parse

    original = b"""<h1>Example</h1><div class="provider-row"><span class="provider-row__lang">Deutsch Dub</span>
      <div data-provider-chip aria-label="VOE" data-movie-link-id="42" data-p="old-token">
      <span class="provider-chip__metadata-tag">WEB</span><span class="provider-chip__metadata-tag">720p</span></div></div>"""
    selected = parse(original, "detail", "/movies/example").offers[0]
    changed = (
        original.replace(b"Deutsch Dub", b"deutsch   DUB")
        .replace(b">WEB<", b">web<")
        .replace(b"720p", b"720P")
        .replace(b"old-token", b"new-token")
    )
    assert (
        _filmo_offer_token(
            changed, {**selected, "path": "/movies/example"}, selected["variant_anchor"]
        )
        == "new-token"
    )


def test_filmo_ephemeral_token_lookup_survives_duplicate_offer_chips():
    from app.catalog.filmo_resolution import _filmo_offer_token
    from catalog_core.providers import filmo

    detail = b"""<h1>Example</h1>
      <div class="provider-row"><span class="provider-row__lang">Deutsch</span>
        <div data-provider-chip aria-label="VOE" data-movie-link-id="42" data-p="duplicate-one"><span class="provider-chip__metadata-tag">720p</span></div>
        <div data-provider-chip aria-label="VOE" data-movie-link-id="42" data-p="duplicate-two"><span class="provider-chip__metadata-tag">720p</span></div>
      </div>
      <div class="provider-row"><span class="provider-row__lang">Deutsch</span>
        <div data-provider-chip aria-label="Byse" data-movie-link-id="84" data-p="selected-token"><span class="provider-chip__metadata-tag">BluRay</span></div>
      </div>"""
    offers = filmo.parse(detail, "detail", "/movies/example").offers
    selected = next(item for item in offers if item["host"] == "Byse")
    assert (
        _filmo_offer_token(
            detail, {**selected, "path": "/movies/example"}, selected["variant_anchor"]
        )
        == "selected-token"
    )


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
