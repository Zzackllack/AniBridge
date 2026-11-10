"""Generated minimized movie markup; no catalog, media or language inference."""

import json

import pytest

from catalog_core.providers.megakino import parse

ORIGIN = "https://movies.invalid"
PATH = "/films/1-example.html"


def field(text="2024", href="/xfsearch/release_date/2024/"):
    return f'<div class="pmovie__year"><span>Country</span>, <span><a href="{href}">{text}</a></span>, 106 min</div>'


def detail(year_html, structured_year=None):
    metadata = ""
    if structured_year is not None:
        record = {
            "@type": "Movie",
            "datePublished": str(structured_year),
            "url": ORIGIN + PATH,
        }
        metadata = f'<script type="application/ld+json">{json.dumps(record)}</script>'
    return f'<html><body><h1>Observed Example</h1>{year_html}{metadata}<iframe src="https://host.invalid/private"></iframe><p>auf Deutsch / 1999</p></body></html>'.encode()


def test_scoped_year_anchor_is_metadata_without_selectable_language():
    page = parse(detail(field("\n" + " " * 64 + "2024")), "detail", PATH, origin=ORIGIN)
    assert page.title == "Observed Example" and page.year == 2024
    assert page.languages == () and page.unknown_languages == 1
    assert page.explicit_imdb is None and "private" not in repr(page)


@pytest.mark.parametrize(
    "markup",
    [
        '<div class="pmovie__year">2024</div>',
        "<div class>2024</div>",
        '<div class="year"><a href="/xfsearch/release_date/2024/">2024</a></div>',
    ],
)
def test_generic_year_url_and_website_language_remain_unknown(markup):
    page = parse(detail(markup), "detail", PATH, origin=ORIGIN)
    assert page.year is None and page.languages == ()


@pytest.mark.parametrize(
    "markup",
    [
        field() + field(),
        field("1799", "/xfsearch/release_date/1799/"),
        field("2201", "/xfsearch/release_date/2201/"),
        field("2024 / 2025"),
        field("2" * 33),
        field("2023"),
        field("2024", "https://foreign.invalid/xfsearch/release_date/2024/"),
        field("2024", "/xfsearch/release_date/2024/?x=unknown"),
        field().replace("</div>", ""),
    ],
)
def test_ambiguous_invalid_foreign_or_unclosed_year_rejects(markup):
    with pytest.raises(ValueError):
        parse(detail(markup), "detail", PATH, origin=ORIGIN)


def test_structured_and_observed_year_must_agree():
    assert parse(detail(field(), 2024), "detail", PATH, origin=ORIGIN).year == 2024
    with pytest.raises(ValueError, match="conflicting movie year"):
        parse(detail(field(), 2025), "detail", PATH, origin=ORIGIN)


def test_unclosed_structural_tag_is_rejected():
    body = detail("").replace(b"</body>", b"<div>orphan</body>")
    with pytest.raises(ValueError, match="incomplete movie document"):
        parse(body, "detail", PATH, origin=ORIGIN)


def test_player_and_language_metadata_are_bounded():
    players = b"".join(
        b'<iframe src="https://host.invalid/%d"></iframe>' % index
        for index in range(1000)
    )
    with pytest.raises(ValueError, match="movie player overflow"):
        parse(
            detail("").replace(b"</body>", players + b"</body>"),
            "detail",
            PATH,
            origin=ORIGIN,
        )

    languages = b"".join(
        b'<iframe src="https://host.invalid/%d" data-language-label="label-%d"></iframe>'
        % (index, index)
        for index in range(65)
    )
    with pytest.raises(ValueError, match="movie language overflow"):
        parse(
            detail("").replace(b"</body>", languages + b"</body>"),
            "detail",
            PATH,
            origin=ORIGIN,
        )
