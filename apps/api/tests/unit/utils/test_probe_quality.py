from app.utils import probe_quality


def test_probe_episode_quality_resolves_fallback_chain_once(monkeypatch):
    episode = object()
    resolution_calls: list[tuple[object, str | None, str]] = []

    monkeypatch.setattr(probe_quality, "build_episode", lambda **_kwargs: episode)

    def _resolve(ep, *, preferred, language):
        resolution_calls.append((ep, preferred, language))
        raise RuntimeError("all hosts unavailable")

    monkeypatch.setattr(probe_quality, "get_direct_url_with_fallback", _resolve)

    result = probe_quality.probe_episode_quality(
        slug="oshi-no-ko",
        season=1,
        episode=1,
        language="German Dub",
        preferred_host="VOE",
        site="aniworld.to",
    )

    assert result == (False, None, None, None, None)
    assert resolution_calls == [(episode, "VOE", "German Dub")]


def test_probe_episode_quality_probes_resolved_url(monkeypatch):
    episode = object()
    monkeypatch.setattr(probe_quality, "build_episode", lambda **_kwargs: episode)
    monkeypatch.setattr(
        probe_quality,
        "get_direct_url_with_fallback",
        lambda ep, *, preferred, language: ("https://video.example/master.m3u8", "VOE"),
    )
    monkeypatch.setattr(
        probe_quality,
        "probe_episode_quality_once",
        lambda url, timeout: (1080, "h264", {"url": url, "timeout": timeout}),
    )

    result = probe_quality.probe_episode_quality(
        slug="oshi-no-ko",
        season=1,
        episode=1,
        language="German Dub",
        timeout=4.0,
        site="aniworld.to",
    )

    assert result == (
        True,
        1080,
        "h264",
        "VOE",
        {"url": "https://video.example/master.m3u8", "timeout": 4.0},
    )
