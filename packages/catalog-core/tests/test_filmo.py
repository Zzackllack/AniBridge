from pathlib import Path

import pytest

from catalog_core.json_codec import ContractError
from catalog_core.providers.filmo import offer_metadata, parse
from catalog_core.release_metadata import validate

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_listing_returns_movie_paths_and_next_page_only() -> None:
    page = parse(fixture("filmo-listing.html"), "listing")

    assert [(link.path, link.name) for link in page.links] == [
        ("/movies/example-film", "Example Film")
    ]
    assert page.next_pages == ("/movies?page=2",)


def test_listing_accepts_complete_html_fragment_from_worker_fixtures() -> None:
    page = parse(
        b'<div class="movie-poster-grid-card">'
        b'<a href="/movies/film-one">Observed Film</a></div>',
        "listing",
        "/movies",
    )

    assert page.links[0].path == "/movies/film-one"


def test_listing_uses_the_configured_origin_and_rejects_foreign_cards():
    body = fixture("filmo-listing.html").replace(
        b"https://filmo.to", b"https://mirror.example"
    )
    page = parse(body, "listing", origin="https://mirror.example")
    assert page.links[0].path == "/movies/example-film"
    assert page.next_pages == ("/movies?page=2",)
    with pytest.raises(ContractError, match="foreign Filmo link"):
        parse(body, "listing")


def test_detail_preserves_offer_context_without_player_tokens() -> None:
    page = parse(fixture("filmo-detail.html"), "detail", "/movies/example-film")

    assert page.title == "Example Film"
    assert page.year == 2022
    assert len(page.offers) == 3
    mixed = page.offers[0]
    assert mixed["native_id"] == "1001"
    assert mixed["language_label"] == "Japanese Sub / German Dub"
    assert mixed["audio_languages"] == ["deu"]
    assert mixed["subtitle_languages"] == ["jpn"]
    assert mixed["audio_role"] == "dubbed"
    assert mixed["quality"] == {
        "labels": ["WEB", "720p"],
        "source": "web",
        "resolution": 720,
    }
    assert page.offers[1]["audio_languages"] == ["spa"]
    assert page.offers[1]["subtitle_languages"] is None
    assert page.offers[2]["audio_languages"] == ["und"]
    assert all("token" not in offer for offer in page.offers)
    assert all("SYNTHETIC_SECRET_TOKEN" not in repr(offer) for offer in page.offers)
    assert len({offer["variant_anchor"] for offer in page.offers}) == 3
    assert all(validate(offer) == offer for offer in page.offers)


@pytest.mark.parametrize(
    ("label", "audio", "subtitles", "role"),
    [
        ("Italian", ["ita"], None, "unknown"),
        ("Spanish", ["spa"], None, "unknown"),
        ("Englische", ["eng"], None, "unknown"),
        ("Französisch", ["fra"], None, "unknown"),
        ("JPN Sub / GER Dub", ["deu"], ["jpn"], "dubbed"),
        ("Original Japanese", ["jpn"], None, "original"),
        ("UND", ["und"], None, "unknown"),
    ],
)
def test_declared_languages_are_not_inferred_from_movie_origin(
    label: str, audio: list[str], subtitles: list[str] | None, role: str
) -> None:
    from catalog_core.providers.filmo import _language_facts

    assert _language_facts(label) == (audio, subtitles, role)


def test_detail_rejects_conflicting_duplicate_identity() -> None:
    body = (
        fixture("filmo-detail.html")
        .replace(
            '<span class="provider-row__lang">Español</span>'.encode(),
            '<span class="provider-row__lang">Japanese Sub / German Dub</span>'.encode(),
        )
        .replace(b'aria-label="Byse"', b'aria-label="VOE"', 1)
    )

    with pytest.raises(ContractError, match="ambiguous duplicate"):
        parse(body, "detail", "/movies/example-film")


@pytest.mark.parametrize(
    ("label", "audio", "subtitles", "role"),
    [
        (
            "English / Original mit deutschen Untertiteln",
            ["eng"],
            ["deu"],
            "original",
        ),
        ("German Sub", ["und"], ["deu"], "unknown"),
        ("Japanese + German subtitles", ["jpn"], ["deu"], "unknown"),
        ("Sub: German, Audio: Japanese", ["jpn"], ["deu"], "unknown"),
        ("English Dub German Sub", ["eng"], ["deu"], "dubbed"),
        ("Korean Audio / German Subtitles", ["kor"], ["deu"], "unknown"),
        ("Unknown Audio / German Sub", ["und"], ["deu"], "unknown"),
        (
            "German Dub + German Sub",
            ["deu"],
            ["deu"],
            "dubbed",
        ),
        ("Deutsch / English", ["deu", "eng"], None, "unknown"),
        ("English und German", ["deu", "eng"], None, "unknown"),
        ("French, Korean, Russian", ["fra", "kor", "rus"], None, "unknown"),
        ("Turkish / Arabic / Portuguese", ["ara", "por", "tur"], None, "unknown"),
        (
            "Chinese / Hindi / Polish / Dutch",
            ["hin", "nld", "pol", "zho"],
            None,
            "unknown",
        ),
        ("Thai", ["und"], None, "unknown"),
    ],
)
def test_mixed_language_labels_separate_subtitles_from_audio(
    label: str, audio: list[str], subtitles: list[str] | None, role: str
) -> None:
    from catalog_core.providers.filmo import _language_facts

    assert _language_facts(label) == (audio, subtitles, role)


def test_offer_anchor_is_stable_across_cosmetic_language_changes() -> None:
    first = offer_metadata("1001", "VOE", "Deutsch / English", ["720p"])
    second = offer_metadata("1001", "voe", "  DEUTSCH   /  ENGLISH ", ["1080p"])
    different_row = offer_metadata("1001", "VOE", "UND", ["720p"])

    assert first["variant_anchor"] == second["variant_anchor"]
    assert first["variant_anchor"] != different_row["variant_anchor"]


def test_conflicting_quality_claims_stay_unknown() -> None:
    offer = offer_metadata("1001", "VOE", "English", ["WEB", "BluRay", "720p", "1080p"])

    assert offer["quality"] == {
        "labels": ["WEB", "BluRay", "720p", "1080p"],
        "source": "unknown",
        "resolution": None,
    }


@pytest.mark.parametrize(
    ("labels", "source", "resolution"),
    [
        (["BluRay 720p"], "bluray", 720),
        (["WEB"], "web", None),
        (["WEB", "DL"], "web", None),
        (["WEB-DL 1080p"], "webdl", 1080),
        (["Camera 720p"], "unknown", 720),
        (["720p and 1080p"], "unknown", None),
        (["WEB BluRay 720p"], "unknown", 720),
    ],
)
def test_quality_tokens_require_explicit_source_and_abstain_on_conflicts(
    labels: list[str], source: str, resolution: int | None
) -> None:
    offer = offer_metadata("1001", "VOE", "English", labels)

    assert offer["quality"] == {
        "labels": labels,
        "source": source,
        "resolution": resolution,
    }


def test_unknown_audio_rows_count_distinct_labels_without_dropping_offers() -> None:
    body = b"""<!doctype html><html><body>
      <h1>Example Film</h1><div class="provider-rows">
        <div class="provider-row"><span class="provider-row__lang">German Sub</span>
          <button data-provider-chip data-movie-link-id="1001" aria-label="VOE"></button>
          <button data-provider-chip data-movie-link-id="1002" aria-label="Byse"></button>
        </div>
      </div></body></html>"""
    page = parse(body, "detail", "/movies/example-film")

    assert page.unknown_languages == 1
    assert len(page.offers) == 2
    assert all(offer["audio_languages"] == ["und"] for offer in page.offers)


def test_empty_provider_rows_are_unavailable_but_missing_rows_are_a_parse_gap() -> None:
    empty_providers = b"""<!doctype html><html><body>
      <div id="movie-detail-page"></div><h1>Example Film</h1>
      <div class="provider-rows"></div>
    </body></html>"""
    assert (
        parse(empty_providers, "detail", "/movies/example-film").availability
        == "unavailable"
    )
    missing_providers = empty_providers.replace(
        b'<div class="provider-rows"></div>', b""
    )

    with pytest.raises(ContractError, match="missing provider rows"):
        parse(missing_providers, "detail", "/movies/example-film")
