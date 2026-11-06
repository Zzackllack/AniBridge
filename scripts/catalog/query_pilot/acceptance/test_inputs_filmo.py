"""Offline coverage of Filmo variant selection and generated source inputs."""

from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path

import pytest
import httpx
from catalog_core.providers import filmo
from app.core.downloader import provider_policy
from app.catalog.media_download import transfer

import filmo_fixture


HOOK = Path(__file__).parent / "filmo_hooks" / "sitecustomize.py"


def load_hook():
    spec = importlib.util.spec_from_file_location("filmo_acceptance_inputs", HOOK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    original_client = httpx.Client
    original_validate = provider_policy._validate_request_url
    httpx_logger = logging.getLogger("httpx")
    original_log_level = httpx_logger.level
    try:
        spec.loader.exec_module(module)
    finally:
        # sitecustomize normally owns these process-wide patches. Unit tests
        # restore them immediately to avoid changing neighboring test cases.
        httpx.Client = original_client
        provider_policy._validate_request_url = original_validate
        httpx_logger.setLevel(original_log_level)
    return module


def test_fixture_rejects_unexpected_external_urls_before_networking():
    fixture = load_hook()
    with pytest.raises(ValueError, match="fixed generated Filmo inputs"):
        fixture.validate("https://unexpected.example/video.mp4")

    calls = []

    class Fallback(httpx.BaseTransport):
        def handle_request(self, request):
            calls.append(request.url.host)
            return httpx.Response(200, content=b"{}")

    transport = fixture.Transport(Fallback())
    for target in (
        "https://unexpected.example/video.mp4",
        "https://api:8000/health",
        "http://api:9999/health",
    ):
        with pytest.raises(ValueError, match="disposable acceptance services"):
            transport.handle_request(httpx.Request("GET", target))
    assert calls == []
    assert (
        transport.handle_request(
            httpx.Request("GET", "http://api:8000/health")
        ).status_code
        == 200
    )
    assert calls == ["api"]


def test_generated_parser_fixture_contains_only_declared_metadata() -> None:
    listing = filmo.parse(
        filmo_fixture.LISTING_HTML.encode(),
        "listing",
        "/movies",
        origin=filmo_fixture.ORIGIN,
    )
    page = filmo.parse(
        filmo_fixture.DETAIL_HTML.encode(),
        "detail",
        filmo_fixture.MOVIE_PATH,
        origin=filmo_fixture.ORIGIN,
    )

    assert [(link.path, link.name) for link in listing.links] == [
        (filmo_fixture.MOVIE_PATH, filmo_fixture.TITLE)
    ]
    assert page.title == filmo_fixture.TITLE
    assert page.year == filmo_fixture.YEAR
    assert {offer["native_id"] for offer in page.offers} == {"42", "84"}
    assert len({offer["variant_anchor"] for offer in page.offers}) == 2
    assert all(offer["audio_languages"] == ["deu", "eng"] for offer in page.offers)
    assert all(offer["subtitle_languages"] is None for offer in page.offers)
    assert all(offer["language_label"] == "Deutsch / English" for offer in page.offers)
    assert all(offer["audio_role"] == "unknown" for offer in page.offers)
    assert all(offer["subtitle_mode"] == "unknown" for offer in page.offers)
    assert {tuple(offer["quality"]["labels"]) for offer in page.offers} == {
        ("WEB", "720p"),
        ("BluRay", "720p"),
    }
    serialized = repr(page.offers)
    assert "fixture-p-" not in serialized
    assert "fixture-csrf" not in serialized
    assert "fixture.invalid" not in serialized


def test_generated_byse_caption_route_is_fixed_and_returns_only_vtt(
    tmp_path: Path,
):
    fixture = load_hook()
    fixture.MEDIA = tmp_path / "generated.mp4"
    fixture.MEDIA.write_bytes(b"placeholder media")

    class Fallback(httpx.BaseTransport):
        def handle_request(self, request):
            raise AssertionError("closed fixture route must not reach network")

    transport = fixture.Transport(Fallback())
    response = transport.handle_request(
        httpx.Request(
            "GET",
            "https://192.0.2.77/captions/generated-german.vtt",
            headers={"Host": "media.fixture.invalid"},
        )
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/vtt")
    assert response.read() == filmo_fixture.CAPTION_VTT
    assert fixture.CAPTION_CHOICES == ["german-vtt"]

    for target in (
        "https://192.0.2.77/captions/other.vtt",
        "https://192.0.2.77/captions/generated-german.vtt?token=not-admitted",
    ):
        with pytest.raises(ValueError, match="undeclared generated Filmo request"):
            transport.handle_request(
                httpx.Request(
                    "GET",
                    target,
                    headers={"Host": "media.fixture.invalid"},
                )
            )


@pytest.mark.parametrize(
    ("native_id", "expected_variant", "expected_source"),
    [
        ("42", "primary", "web"),
        ("84", "alternate", "bluray"),
    ],
)
def test_resolver_selects_exact_offer_and_decodes_generated_byse_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    native_id: str,
    expected_variant: str,
    expected_source: str,
) -> None:
    fixture = load_hook()
    fixture.CHUNK_DELAY_S = 0
    fixture.MEDIA = tmp_path / "generated.mp4"
    media_bytes = b"synthetic-mp4-prefix\x00" * 4096
    fixture.MEDIA.write_bytes(media_bytes)
    fixture.VARIANT_CHOICES.clear()

    from app.catalog.aniworld_resolution import resolve
    from app.catalog.media_download import SilentLog
    from app.catalog.media_transport import TransferState, VerifiedRH
    from app.catalog.resolution_transport import Budget
    from yt_dlp.networking import Request

    page = filmo.parse(
        filmo_fixture.DETAIL_HTML.encode(),
        "detail",
        filmo_fixture.MOVIE_PATH,
        origin=filmo_fixture.ORIGIN,
    )
    metadata = next(item for item in page.offers if item["native_id"] == native_id)
    assert metadata["quality"]["source"] == expected_source
    payload = {
        "provider": "filmo.to",
        "kind": "movie",
        "path": filmo_fixture.MOVIE_PATH,
        "variant_anchor": metadata["variant_anchor"],
        "release_metadata": metadata,
    }

    budget = Budget(
        client=fixture.Client(),
        validate_url=fixture.validate,
        seconds=10,
        requests=10,
        body_bytes=2 * 1024**2,
    )
    try:
        resolved = resolve(payload, filmo_fixture.ORIGIN, ("Byse",), budget)
    finally:
        budget.close()

    assert len(resolved.captions) == 1
    caption = resolved.captions[0]
    assert caption.url == filmo_fixture.CAPTION_URL
    assert (caption.language, caption.format) == ("deu", "vtt")

    import httpx
    from app.catalog import media_transport

    monkeypatch.setattr(httpx, "Client", fixture.Client)
    monkeypatch.setattr(media_transport, "_validate_request_url", fixture.validate)
    fixture.CAPTION_CHOICES.clear()
    transferred = transfer(
        resolved.url,
        tmp_path / "transfer",
        lambda _update: None,
        selection=metadata,
        captions=resolved.captions,
    )
    assert len(transferred) == 2
    assert transferred[1].suffix == ".vtt"
    assert transferred[1].read_bytes() == filmo_fixture.CAPTION_VTT
    track_manifest = json.loads((tmp_path / "transfer" / "tracks.json").read_text())
    assert track_manifest["tracks"] == [
        {
            "file": transferred[0].name,
            "kind": "video",
            "language": None,
            "format": None,
        },
        {
            "file": transferred[1].name,
            "kind": "subtitle",
            "language": "deu",
            "format": "vtt",
        },
    ]
    assert fixture.CAPTION_CHOICES == ["german-vtt"]

    state = TransferState(tmp_path)
    handler = VerifiedRH(state=state, logger=SilentLog())
    response = handler.send(Request(resolved.url, headers={"Range": "bytes=0-4095"}))
    try:
        assert response.status == 206
        prefix = response.read(4096)
    finally:
        response.close()
        handler.close()

    assert resolved.host == "Byse"
    assert resolved.url == filmo_fixture.MEDIA_URL
    assert prefix == media_bytes[:4096]
    assert fixture.VARIANT_CHOICES == [expected_variant]
