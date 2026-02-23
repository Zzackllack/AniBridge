from pathlib import Path

from app.providers.sto.v2 import (
    build_episode_url,
    parse_episode_providers,
    parse_release_at_from_sto_html,
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


def test_parse_release_at_from_sto_html_prefers_title_timestamp() -> None:
    html_text = """
    <span class="flex-grow-1">
      <span title="Feb 23, 2026 20:47 Uhr">
        Veröffentlicht am February 23, 2026
      </span>
    </span>
    """

    parsed = parse_release_at_from_sto_html(html_text)

    assert parsed is not None
    assert parsed.isoformat() == "2026-02-23T19:47:00+00:00"
