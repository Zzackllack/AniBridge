import time

import pytest


def test_try_get_direct_times_out_and_returns_none(monkeypatch):
    import app.core.downloader.provider_resolution as provider_resolution

    class SlowEpisode:
        def get_direct_link(self, provider_name: str, language: str) -> str:
            time.sleep(0.2)
            return f"{provider_name}:{language}"

    monkeypatch.setattr(
        provider_resolution,
        "PROVIDER_DIRECT_LINK_TIMEOUT_SECONDS",
        0.05,
    )

    started_at = time.monotonic()
    result = provider_resolution._try_get_direct(
        SlowEpisode(),
        "VOE",
        "German Dub",
    )

    assert result is None
    assert time.monotonic() - started_at < 0.15


def test_try_get_direct_only_skips_same_provider_while_worker_is_running(monkeypatch):
    import app.core.downloader.provider_resolution as provider_resolution

    class SlowEpisode:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def get_direct_link(self, provider_name: str, language: str) -> str:
            self.calls.append(provider_name)
            if provider_name == "VOE":
                time.sleep(0.2)
            return f"{provider_name}:{language}"

    monkeypatch.setattr(
        provider_resolution,
        "PROVIDER_DIRECT_LINK_TIMEOUT_SECONDS",
        0.05,
    )

    episode = SlowEpisode()

    assert provider_resolution._try_get_direct(episode, "VOE", "German Dub") is None
    assert provider_resolution._try_get_direct(episode, "VOE", "German Dub") is None
    assert (
        provider_resolution._try_get_direct(episode, "Doodstream", "German Dub")
        == "Doodstream:German Dub"
    )
    assert episode.calls == ["VOE", "Doodstream"]


def test_try_get_direct_handles_episode_without_weakref_support(monkeypatch):
    import app.core.downloader.provider_resolution as provider_resolution

    class SlottedEpisode:
        __slots__ = ("calls",)

        def __init__(self) -> None:
            self.calls: list[str] = []

        def get_direct_link(self, provider_name: str, language: str) -> str:
            self.calls.append(provider_name)
            if provider_name == "VOE":
                time.sleep(0.2)
            return f"{provider_name}:{language}"

    monkeypatch.setattr(
        provider_resolution,
        "PROVIDER_DIRECT_LINK_TIMEOUT_SECONDS",
        0.05,
    )

    episode = SlottedEpisode()

    assert provider_resolution._try_get_direct(episode, "VOE", "German Dub") is None
    assert provider_resolution._try_get_direct(episode, "VOE", "German Dub") is None
    assert (
        provider_resolution._try_get_direct(episode, "Doodstream", "German Dub")
        == "Doodstream:German Dub"
    )
    assert episode.calls == ["VOE", "Doodstream"]


def test_get_direct_url_with_fallback_continues_after_timeout(monkeypatch):
    import app.core.downloader.provider_resolution as provider_resolution

    class Episode:
        def get_direct_link(self, provider_name: str, language: str) -> str:
            if provider_name == "VOE":
                time.sleep(0.2)
            return f"{provider_name}:{language}"

    monkeypatch.setattr(
        provider_resolution,
        "PROVIDER_DIRECT_LINK_TIMEOUT_SECONDS",
        0.05,
    )
    monkeypatch.setattr(provider_resolution, "PROVIDER_ORDER", ["VOE", "Doodstream"])

    assert provider_resolution.get_direct_url_with_fallback(
        Episode(),
        preferred=None,
        language="German Dub",
    ) == ("Doodstream:German Dub", "Doodstream")


def test_try_get_direct_raises_for_missing_language(monkeypatch):
    import app.core.downloader.provider_resolution as provider_resolution
    from app.core.downloader.errors import LanguageUnavailableError

    class MissingLanguageEpisode:
        def get_direct_link(self, provider_name: str, language: str) -> str:
            del provider_name, language
            raise ValueError(
                "No provider found for language 'German Dub'. "
                "Available languages: ['English Sub', 'German Sub']"
            )

    monkeypatch.setattr(
        provider_resolution,
        "PROVIDER_DIRECT_LINK_TIMEOUT_SECONDS",
        0.05,
    )

    with pytest.raises(LanguageUnavailableError) as exc_info:
        provider_resolution._try_get_direct(
            MissingLanguageEpisode(),
            "VOE",
            "German Dub",
        )

    assert exc_info.value.available == ["English Sub", "German Sub"]
