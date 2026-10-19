"""Frozen subtitle selection from metadata only; no player or media request."""

from app.catalog.aniworld_resolution import offers


def test_observed_subtitle_offer_never_selects_english_audio_instead():
    body = '<button data-play-url="/subtitle-redirect" data-provider-name="VOE" data-language-label="Ger-Sub"></button><button data-play-url="/audio-redirect" data-provider-name="Vidoza" data-language-label="Englisch"></button>'
    selected = offers(body, "https://configured.example", "de-sub", "s.to")
    assert selected == {"VOE": "https://configured.example/subtitle-redirect"}
    assert offers(body, "https://configured.example", "en-dub", "s.to") == {
        "Vidoza": "https://configured.example/audio-redirect"
    }
