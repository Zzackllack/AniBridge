from pathlib import Path

import pytest

from app.core.downloader.errors import UnsupportedProviderResponseError
from app.core.downloader.errors import ProviderVerificationRequiredError
import app.providers.sto.v2 as sto_v2
from app.providers.sto.v2 import (
    build_episode_url,
    parse_episode_providers,
    parse_episode_provider_data,
    parse_language_id,
)


def _read_episode_fixture() -> str:
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "specs").is_dir():
            break
        current = current.parent
    path = current / "specs" / "007-sto-v2-support" / "html" / "2-episode.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return """
    <div id="episode-links">
      <button data-play-url="/r?t=token1" data-provider-name="VOE" data-language-label="Deutsch" data-language-id="1"></button>
      <button data-play-url="/r?t=token2" data-provider-name="Doodstream" data-language-label="Deutsch" data-language-id="1"></button>
      <button data-play-url="/r?t=token3" data-provider-name="VOE" data-language-label="Englisch" data-language-id="2"></button>
    </div>
    """


def test_build_episode_url() -> None:
    url = build_episode_url("https://s.to/", "9-1-1", 1, 2)
    assert url == "https://s.to/serie/9-1-1/staffel-1/episode-2"


def test_parse_language_id_from_raw() -> None:
    assert parse_language_id("1", None) == 1
    assert parse_language_id("2", "Deutsch") == 2


def test_parse_language_id_from_label() -> None:
    assert parse_language_id(None, "Deutsch") == 1
    assert parse_language_id(None, "Englisch") == 2
    assert parse_language_id(None, "German Sub") == 3


def test_parse_episode_providers_from_fixture() -> None:
    html_text = _read_episode_fixture()
    providers, languages, language_names = parse_episode_providers(
        html_text, "https://s.to"
    )

    assert "VOE" in providers
    assert "Doodstream" in providers
    assert 1 in providers["VOE"]
    assert 2 in providers["VOE"]
    assert 1 in providers["Doodstream"]

    assert 1 in languages
    assert 2 in languages
    assert "German Dub" in language_names
    assert "English Dub" in language_names


def test_parse_episode_provider_data_uses_public_language_labels() -> None:
    provider_data = parse_episode_provider_data(
        _read_episode_fixture(),
        "https://s.to",
    )

    assert provider_data["German Dub"]["VOE"].startswith("https://s.to/r?")
    assert provider_data["English Dub"]["VOE"].startswith("https://s.to/r?")


def test_parse_episode_provider_data_rejects_empty_markup() -> None:
    with pytest.raises(UnsupportedProviderResponseError, match="no recognized"):
        parse_episode_provider_data("<html><body>changed</body></html>", "https://s.to")


def test_parse_episode_provider_data_rejects_external_redirect() -> None:
    html = """
    <button data-play-url="https://other.example/r?t=secret"
            data-provider-name="VOE" data-language-id="1"></button>
    """
    with pytest.raises(UnsupportedProviderResponseError, match="outside"):
        parse_episode_provider_data(html, "https://configured.example")


def test_fetch_episode_html_reports_bounded_verification_error(monkeypatch) -> None:
    monkeypatch.setattr(sto_v2, "PROVIDER_CHALLENGE_BACKOFF_SECONDS", 45)

    def _blocked(*_args, **_kwargs):
        raise ProviderVerificationRequiredError(
            "blocked",
            stage="Serienstream episode metadata",
            status_code=403,
            host="configured.example",
        )

    monkeypatch.setattr(sto_v2, "fetch_verified_response", _blocked)

    with pytest.raises(ProviderVerificationRequiredError) as exc_info:
        sto_v2.fetch_episode_html(
            "https://configured.example/serie/show/staffel-1/episode-1",
            base_url="https://configured.example",
        )
    assert exc_info.value.retry_after_seconds == 45
