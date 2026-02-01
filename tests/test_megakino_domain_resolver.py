from __future__ import annotations

from dataclasses import dataclass

import app.utils.domain_resolver as domain_resolver


def test_is_sitemap_payload_accepts_valid_urlset():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/films/1-test.html</loc></url>
    </urlset>
    """
    assert domain_resolver._is_sitemap_payload(xml) is True


def test_is_sitemap_payload_rejects_invalid_xml():
    assert domain_resolver._is_sitemap_payload("<urlset>") is False


def test_is_sitemap_payload_rejects_html():
    html = "<!doctype html><html><head></head><body>wait</body></html>"
    assert domain_resolver._is_sitemap_payload(html) is False


def test_parse_mirror_domains_parses_urls_and_hosts():
    raw = """
    # comment
    https://megakino1.to
    megakino1.fit
    http://megakino.cloud/some/path
    not a domain
    <script>alert(1)</script>
    """
    domains = domain_resolver._parse_mirror_domains(raw)
    assert domains == ["megakino1.to", "megakino1.fit", "megakino.cloud"]


@dataclass
class _DummyResponse:
    status_code: int
    text: str
    url: str


def test_fetch_megakino_mirror_domains_skips_html(monkeypatch):
    calls: list[str] = []

    def fake_get(url, *, timeout=0, allow_redirects=True, headers=None):
        calls.append(url)
        if "first.example" in url:
            return _DummyResponse(200, "<!doctype html><html>bad</html>", url)
        return _DummyResponse(200, "https://megakino1.to\nmegakino1.fit", url)

    monkeypatch.setattr(
        domain_resolver,
        "MEGAKINO_DOMAIN_CANDIDATES",
        ["first.example", "second.example"],
    )
    monkeypatch.setattr(domain_resolver, "http_get", fake_get)

    domains = domain_resolver.fetch_megakino_mirror_domains(timeout=1)
    assert domains == ["megakino1.to", "megakino1.fit"]
    assert len(calls) == 2


def test_fetch_megakino_mirror_domains_falls_back_to_sitemap(monkeypatch):
    calls: list[str] = []
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://megakino1.org/</loc></url>
    </urlset>
    """

    def fake_get(url, *, timeout=0, allow_redirects=True, headers=None):
        calls.append(url)
        if url.endswith("/mirrors.txt"):
            return _DummyResponse(200, "<!doctype html><html>bad</html>", url)
        if url.endswith("/sitemap.xml"):
            return _DummyResponse(200, sitemap_xml, "https://megakino1.org/sitemap.xml")
        return _DummyResponse(404, "", url)

    monkeypatch.setattr(
        domain_resolver,
        "MEGAKINO_DOMAIN_CANDIDATES",
        ["first.example"],
    )
    monkeypatch.setattr(domain_resolver, "http_get", fake_get)

    domains = domain_resolver.fetch_megakino_mirror_domains(timeout=1)
    assert domains == ["megakino1.org"]
    assert any("/sitemap.xml" in call for call in calls)
