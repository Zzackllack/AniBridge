"""Small sanitized provider row shapes, no playable URLs or live access."""

import pytest
from catalog_core.providers.aniworld import parse as ani_parse
from catalog_core.providers.sto import parse as sto_parse


@pytest.mark.parametrize(
    "provider,parse,prefix,row",
    [
        (
            "aniworld.to",
            ani_parse,
            "/anime/stream/example",
            '<tr itemtype="http://schema.org/Episode"><td class="seasonEpisodeTitle"><a itemprop="url" href="{ep}"><strong>Erste Geschichte</strong><span>First story</span></a></td><td class="editFunctions"><img class="flag" src="/public/img/german.svg"><img class="flag" src="/public/img/japanese-english.svg"></td></tr>',
        ),
        (
            "s.to",
            sto_parse,
            "/serie/example",
            '<tr class="episode-row" onclick="window.location=\'{ep}\'"><td><strong class="episode-title-ger">Erste Geschichte</strong><span class="episode-title-eng">First story</span></td><td><svg class="watch-language svg-flag-german"></svg><svg class="watch-language svg-flag-english"></svg></td></tr>',
        ),
    ],
)
def test_explicit_row_names_flags_and_unknowns(provider, parse, prefix, row):
    season = prefix + "/staffel-1"
    ep = season + "/episode-9"
    body = (
        "<html><body><table>" + row.format(ep=ep) + "</table></body></html>"
    ).encode()
    page = parse(body, "detail", season)
    assert len(page.episodes) == 1 and page.episodes[0].title == "First story"
    assert page.episodes[0].aliases == ("Erste Geschichte",)
    assert page.episodes[0].languages == (
        "de-dub",
        "en-sub" if provider == "aniworld.to" else "en-dub",
    )
    assert page.links[0].path == ep
    wrong = body.replace(b"german.svg", b"unknown.svg").replace(
        b"svg-flag-german", b"svg-flag-unknown"
    )
    assert parse(wrong, "detail", season).episodes[0].unknown_languages == 1


def test_conflicting_rows_and_incomplete_markup_reject():
    season = "/serie/example/staffel-1"
    ep = season + "/episode-1"
    row = f'<tr class="episode-row" onclick="window.location=\'{ep}\'"><td><strong class="episode-title-ger">One</strong></td></tr>'
    body = (
        "<html><body><table>"
        + row
        + row.replace("One", "Two")
        + "</table></body></html>"
    )
    with pytest.raises(ValueError, match="conflicting episode rows"):
        sto_parse(body.encode(), "detail", season)


def test_invalid_optional_imdb_hint_keeps_native_series_without_inventing_id():
    page = ani_parse(
        b'<html><body><h1>Example</h1><a data-imdb="not-an-imdb-id"></a>'
        b'<a href="/anime/stream/example/staffel-1">Season 1</a></body></html>',
        "detail",
        "/anime/stream/example",
    )
    assert page.title == "Example" and page.explicit_imdb is None
    assert [link.path for link in page.links] == ["/anime/stream/example/staffel-1"]


def test_conflicting_valid_imdb_hints_are_still_rejected():
    with pytest.raises(ValueError, match="conflicting explicit IMDb IDs"):
        ani_parse(
            b'<html><body><h1>Example</h1><a data-imdb="tt1234567"></a>'
            b'<a data-imdb="tt7654321"></a>'
            b'<a href="/anime/stream/example/staffel-1">Season 1</a></body></html>',
            "detail",
            "/anime/stream/example",
        )


def test_observed_serienstream_combined_flag_is_subtitle_evidence_only():
    path = "/serie/example/staffel-1/episode-1"
    body = f'<html><body><table><tr class="episode-row" onclick="window.location=\'{path}\'"><td><span class="episode-title-eng">Beginning</span></td><td><svg class="watch-language large svg-flag-english-german"></svg></td></tr></table></body></html>'
    row = sto_parse(body.encode(), "detail", path.rsplit("/", 1)[0]).episodes[0]
    assert row.languages == ("de-sub",) and row.unknown_languages == 0
    unknown = body.replace("svg-flag-english-german", "svg-flag-other")
    row = sto_parse(unknown.encode(), "detail", path.rsplit("/", 1)[0]).episodes[0]
    assert row.languages == () and row.unknown_languages == 1
