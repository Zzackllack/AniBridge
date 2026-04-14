from __future__ import annotations

import warnings

import pytest

import app.hosts as host_registry
from app.hosts import detect_host, resolve_host_url
from app.hosts.base import VideoHost
from app.hosts.bridge import resolve_via_aniworld
from app.hosts.gxplayer import resolve_gxplayer


REPRESENTATIVE_URLS = {
    "VOE": "https://voe.sx/e/abc123",
    "Doodstream": "https://doodstream.com/e/abc123",
    "Filemoon": "https://filemoon.sx/e/abc123",
    "Streamtape": "https://streamtape.com/e/abc123",
    "Vidmoly": "https://vidmoly.to/embed-abc123.html",
    "LoadX": "https://loadx.to/embed/abc123",
    "Luluvdo": "https://luluvdo.com/e/abc123",
    "Vidoza": "https://vidoza.net/embed-abc123",
    "GXPlayer": "https://watch.gxplayer.xyz/embed/abc123",
}


def test_detect_host_matches_known_embed_domain():
    host = detect_host(REPRESENTATIVE_URLS["VOE"])
    assert host is not None
    assert host.name == "VOE"


def test_detect_host_ignores_userinfo_host_confusion():
    host = detect_host("https://voe.sx@evil.example/embed/abc123")
    assert host is None


def test_resolve_host_url_returns_embed_when_unknown():
    direct_url, host_name = resolve_host_url("https://example.invalid/embed/123")
    assert direct_url is None
    assert host_name == "EMBED"


@pytest.mark.parametrize("host_name, url", sorted(REPRESENTATIVE_URLS.items()))
def test_registry_hosts_are_discoverable(host_name: str, url: str):
    host = detect_host(url)
    assert host is not None
    assert host.name == host_name


def test_resolve_host_url_uses_registry(monkeypatch):
    fake_hosts = tuple(
        VideoHost(
            name=host.name,
            hints=host.hints,
            resolver=lambda url, *, expected=host.name: f"https://direct/{expected}",
        )
        for host in host_registry.VIDEO_HOSTS
    )
    monkeypatch.setattr(host_registry, "VIDEO_HOSTS", fake_hosts)
    monkeypatch.setattr(
        host_registry,
        "VIDEO_HOSTS_BY_NAME",
        {host.name: host for host in fake_hosts},
    )

    for host_name, url in REPRESENTATIVE_URLS.items():
        direct_url, resolved_name = resolve_host_url(url)
        assert direct_url == f"https://direct/{host_name}"
        assert resolved_name == host_name


def test_resolve_via_aniworld_falls_back_to_provider_functions(monkeypatch):
    def fake_import_module(name: str):
        if name == "aniworld.extractors.provider.voe":
            raise ImportError("missing provider module")
        if name == "aniworld.extractors":

            class ExtractorsModule:
                provider_functions = {
                    "get_direct_link_from_voe": lambda url: f"{url}/fallback"
                }

            return ExtractorsModule()
        raise AssertionError(f"unexpected module import: {name}")

    monkeypatch.setattr("app.hosts.bridge.prepare_aniworld_home", lambda: None)
    monkeypatch.setattr("app.hosts.bridge.import_module", fake_import_module)

    resolved = resolve_via_aniworld(
        module_name="voe",
        function_name="get_direct_link_from_voe",
        url="https://voe.sx/e/abc123",
        host_name="VOE",
    )

    assert resolved == "https://voe.sx/e/abc123/fallback"


def test_resolve_via_aniworld_propagates_extractor_errors(monkeypatch):
    class ProviderModule:
        @staticmethod
        def get_direct_link_from_voe(url: str) -> str:
            raise ValueError(f"boom: {url}")

    monkeypatch.setattr("app.hosts.bridge.prepare_aniworld_home", lambda: None)
    monkeypatch.setattr(
        "app.hosts.bridge.import_module",
        lambda name: (
            ProviderModule() if name == "aniworld.extractors.provider.voe" else None
        ),
    )

    with pytest.raises(ValueError, match="boom: https://voe.sx/e/abc123"):
        resolve_via_aniworld(
            module_name="voe",
            function_name="get_direct_link_from_voe",
            url="https://voe.sx/e/abc123",
            host_name="VOE",
        )


def test_resolve_gxplayer_accepts_whitespace_and_encodes_values(monkeypatch):
    response = type(
        "Response",
        (),
        {
            "text": '{ "uid" : "uid/with space", "md5" : "hash+slash/", "id" : "video id" }'
        },
    )()
    monkeypatch.setattr(
        "app.hosts.gxplayer.get_megakino_base_url", lambda: "https://megakino.example"
    )
    monkeypatch.setattr("app.hosts.gxplayer.http_get", lambda *args, **kwargs: response)

    resolved = resolve_gxplayer("https://watch.gxplayer.xyz/embed/abc123")

    assert resolved == (
        "https://watch.gxplayer.xyz/m3u8/uid%2Fwith%20space/hash%2Bslash%2F/master.txt"
        "?s=1&id=video+id&cache=1"
    )


def test_megakino_client_warns_for_preferred_provider_alias(monkeypatch):
    from app.providers.megakino.client import MegakinoClient

    client = MegakinoClient(sitemap_url="http://example.com", refresh_hours=0.0)
    monkeypatch.setattr(client, "resolve_url", lambda slug: None)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(ValueError, match="Megakino page not found"):
            client.resolve_direct_url("slug", preferred_provider="VOE")

    assert any(item.category is DeprecationWarning for item in caught)
