from __future__ import annotations

from dataclasses import dataclass
import time

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


def test_fetch_megakino_domain_dedupes_and_prefers_candidate_order(monkeypatch):
    probed: list[str] = []

    monkeypatch.setattr(
        domain_resolver,
        "MEGAKINO_DOMAIN_CANDIDATES",
        ["second.example", "third.example"],
    )
    monkeypatch.setattr(
        domain_resolver,
        "fetch_megakino_mirror_domains",
        lambda timeout=0, **kwargs: ["first.example", "second.example"],
    )

    def fake_probe(base_url: str, timeout=0):
        domain = domain_resolver._normalize_domain(base_url)
        probed.append(domain)
        if domain == "second.example":
            return "second.example"
        return None

    monkeypatch.setattr(domain_resolver, "_probe_megakino_sitemap", fake_probe)

    resolved = domain_resolver.fetch_megakino_domain(timeout=1)
    assert resolved == "second.example"
    assert probed.count("second.example") == 1


def test_fetch_megakino_domain_returns_none_when_all_candidates_fail(monkeypatch):
    monkeypatch.setattr(
        domain_resolver,
        "MEGAKINO_DOMAIN_CANDIDATES",
        ["first.example", "second.example"],
    )
    monkeypatch.setattr(
        domain_resolver,
        "fetch_megakino_mirror_domains",
        lambda timeout=0, **kwargs: [],
    )
    monkeypatch.setattr(
        domain_resolver, "_probe_megakino_sitemap", lambda *a, **k: None
    )

    resolved = domain_resolver.fetch_megakino_domain(timeout=1)
    assert resolved is None


def test_resolver_http_get_applies_hard_wall_time(monkeypatch):
    def fake_get(*args, **kwargs):
        time.sleep(1.0)
        raise RuntimeError("late failure")

    monkeypatch.setattr(domain_resolver, "http_get", fake_get)

    started = time.monotonic()
    try:
        domain_resolver._resolver_http_get(
            "https://example.invalid",
            timeout=0.05,
            allow_redirects=True,
            headers={},
        )
        assert False, "expected RequestException"
    except Exception as exc:
        elapsed = time.monotonic() - started
        assert "resolver wall-time exceeded" in str(exc)
        assert elapsed < 0.5


def test_fetch_megakino_domain_disables_mirror_sitemap_fallback(monkeypatch):
    seen_kwargs: dict[str, object] = {}

    def fake_mirrors(timeout=0, **kwargs):
        seen_kwargs.update(kwargs)
        return []

    monkeypatch.setattr(
        domain_resolver,
        "MEGAKINO_DOMAIN_CANDIDATES",
        [],
    )
    monkeypatch.setattr(domain_resolver, "fetch_megakino_mirror_domains", fake_mirrors)

    resolved = domain_resolver.fetch_megakino_domain(timeout=1)
    assert resolved is None
    assert seen_kwargs.get("include_sitemap_fallback") is False
