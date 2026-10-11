"""Generated structures only; observed pages are never committed fixtures."""

import pytest
from catalog_core.providers.recent import MAX_ENTRIES, parse

EP = "/anime/stream/example/staffel-1/episode-1"


def body(rows):
    return (
        '<html><body><div class="newEpisodeList">' + rows + "</div></body></html>"
    ).encode()


def row(path=EP, flag="german.svg", name="Example"):
    return f'<div class="row"><div><a href="{path}"><strong>{name}</strong></a><img data-src="/public/img/{flag}"/><noscript><img src="/public/img/{flag}"></noscript></div></div>'


def test_stable_variants_deduplicate_flags_and_rows():
    window = parse(
        body(row() + row() + row(flag="japanese-german.svg")),
        "aniworld.to",
        "https://aniworld.to",
    )
    assert [(r.path, r.language) for r in window.entries] == [
        (EP, "de-dub"),
        (EP, "de-sub"),
    ]
    assert window.unknown_languages == 0 and not window.pagination
    assert "img" not in repr(window)


def test_sto_labels_are_not_aniworld_language_keys():
    html = b'<html><body><table class="new-episodes-table"><tbody><tr><td><a href="/serie/example/staffel-0/episode-1">Example</a></td><td><svg title="Englisch"><use href="#flag"></use></svg></td></tr></tbody></table></body></html>'
    window = parse(html, "s.to", "https://serienstream.cx")
    assert window.entries[0].language == "en-dub"
    assert window.entries[0].title == "Example"


def test_unrecognized_flags_and_empty_windows_are_gaps_not_invented_variants():
    window = parse(body(row(flag="unknown.svg")), "aniworld.to", "https://aniworld.to")
    assert window.entries[0].language is None and window.unknown_languages == 1
    assert parse(body(""), "aniworld.to", "https://aniworld.to").entries == ()


@pytest.mark.parametrize(
    "mutant",
    [
        body(row()).removesuffix(b"</html>"),
        b"<html><body>cf-turnstile captcha-form</body></html>",
        body(row("https://evil.invalid" + EP)),
        body(row(EP + "?page=1")),
        body(row(name="")),
        body(row(name="x" * 513)),
        body(row() * (MAX_ENTRIES + 1)),
    ],
)
def test_bounded_hostile_or_truncated_pages_reject(mutant):
    with pytest.raises(ValueError):
        parse(mutant, "aniworld.to", "https://aniworld.to")


def test_pagination_presence_never_claims_a_complete_window():
    window = parse(
        body(row() + '<a href="/neue-episoden?page=2">Next</a>'),
        "aniworld.to",
        "https://aniworld.to",
    )
    assert window.pagination


def test_foreign_and_multiple_targets_in_one_row_reject():
    mutant = row().replace(
        "</strong></a>",
        '</strong></a><a href="' + EP.replace("episode-1", "episode-2") + '">Other</a>',
    )
    with pytest.raises(ValueError, match="ambiguous"):
        parse(body(mutant), "aniworld.to", "https://aniworld.to")


def test_same_origin_absolute_paths_and_films_keep_native_identity():
    movie = "/anime/stream/example/filme/film-1"
    window = parse(
        body(row("https://aniworld.to" + movie)), "aniworld.to", "https://aniworld.to"
    )
    assert window.entries[0].path == movie


def test_known_language_with_unknown_flag_keeps_known_evidence_and_exposes_gap():
    body = b'<html><body><div class="newEpisodeList"><div class="row"><a href="/anime/stream/example/staffel-1/episode-1"><strong>Example</strong></a><img class="flag" src="/public/img/german.svg"><img class="flag" src="/public/img/unknown.svg"></div></div></body></html>'
    window = parse(body, "aniworld.to", "https://aniworld.to")
    assert window.unknown_languages == 1
    assert {v.language for v in window.entries} == {"de-dub"}


def test_observed_gersub_recent_label_does_not_guess_audio():
    from catalog_core.providers.recent import parse

    body = b'<html><body><table class="new-episodes-table"><tr><td><a href="/serie/example/staffel-1/episode-1">Example</a></td><td><svg title="Ger-Sub"></svg></td></tr></table></body></html>'
    window = parse(body, "s.to", "https://serienstream.to")
    assert window.unknown_languages == 0
    assert window.entries[0].language == "de-sub"
