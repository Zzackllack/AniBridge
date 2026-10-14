"""Canonical-path fast proof agrees with the full identity recipe."""

import itertools

import pytest
from catalog_core import identity, schema


@pytest.mark.parametrize(
    "value",
    [
        "/",
        "/anime/stream/title/staffel-0/episode-1",
        "/serie/title-1_a.~b",
        "/a/./b",
        "/a/../b",
        "/a/.",
        "/a/..",
        "/a/",
        "//host/a",
        "/a//b",
        "/a/%2e/b",
        "/a/%2E%2E/b",
        "/a/%2f/b",
        "/a/%5c/b",
        "/a/%25/b",
        "/a/%ZZ",
        "/a/%20b",
        "/a/%c3%a4",
        "/a/%C3%A4",
        "/a/ä",
        "/a/a?query",
        "/a/a#fragment",
        "/a/a\\b",
        "/a/\x00b",
        "/a/\x7fb",
        "/a/foo..bar",
        "/a/.hidden",
        "/a/-_~.",
        "/a/..not-a-segment",
    ],
)
def test_path_proof_matches_normalization_and_rejection(value):
    try:
        expected = identity.path(value) == value
    except ValueError:
        with pytest.raises(ValueError):
            schema._canonical_path(value)
    else:
        assert schema._canonical_path(value) == expected


def test_safe_alphabet_segment_combinations_preserve_recipe():
    # Segment structure is the interesting condition, including adjacent dots.
    # This oracle is the general decode/normalize/quote recipe, not the shortcut.
    segments = ("", ".", "..", "a", ".a", "a.", "..a", "a..", "-_~")
    for pieces in itertools.product(segments, repeat=3):
        value = "/" + "/".join(pieces)
        try:
            expected = identity.path(value) == value
        except ValueError:
            with pytest.raises(ValueError):
                schema._canonical_path(value)
        else:
            assert schema._canonical_path(value) == expected
