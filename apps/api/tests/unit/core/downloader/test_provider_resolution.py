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
