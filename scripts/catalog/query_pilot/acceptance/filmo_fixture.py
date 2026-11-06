"""Closed, synthetic Filmo input shared by the seed and local test hook."""

from __future__ import annotations

import base64
import json

from catalog_core import identity

ORIGIN = "https://fixture.invalid"
MOVIE_PATH = "/movies/generated-client-fixture"
TMDB_MOVIE_ID = "10331"
IMDB_ID = "tt0063350"
TITLE = "Night of the Living Dead"
YEAR = 1968
CANONICAL_IDS = (("tmdb-movie", TMDB_MOVIE_ID), ("imdb", IMDB_ID))


def canonical_mapping_rows(title_id: str, observed_at: int) -> list[tuple]:
    """Return reviewed fixture mappings matching the public movie metadata."""
    return [
        (
            identity.mapping_id("filmo.to", title_id, namespace, external_id),
            title_id,
            namespace,
            external_id,
            "synthetic-v1",
            "reviewed",
            observed_at,
        )
        for namespace, external_id in CANONICAL_IDS
    ]


# These attributes match the parser/resolver's explicit input boundary. Values
# here are synthetic and contain no copied provider titles or credentials.
DETAIL_HTML = f"""<!doctype html>
<html><head><meta name="csrf-token" content="fixture-csrf-v1"></head><body>
<div id="movie-detail-page">
<h1>{TITLE}</h1>
<dl><dt>Release Year</dt><dd>{YEAR}</dd></dl>
<div class="provider-rows">
  <div class="provider-row">
    <span class="provider-row__lang">English Dub German Sub</span>
    <button data-provider-chip data-movie-link-id="42" data-p="fixture-p-primary" aria-label="Byse">
      <span class="provider-chip__metadata-tag">WEB</span>
      <span class="provider-chip__metadata-tag">720p</span>
    </button>
    <button data-provider-chip data-movie-link-id="84" data-p="fixture-p-alternate" aria-label="Byse">
      <span class="provider-chip__metadata-tag">BluRay</span>
      <span class="provider-chip__metadata-tag">720p</span>
    </button>
  </div>
</div>
</body></html>"""

LISTING_HTML = f"""<!doctype html>
<html><head></head><body>
<div class="movie-poster-grid-card"><a href="{MOVIE_PATH}">{TITLE}</a></div>
</body></html>"""

PRIMARY_EMBED = "https://bysefixture.test/d/Abc123"
ALTERNATE_EMBED = "https://bysefixture.test/d/Def456"
MEDIA_URL = "https://media.fixture.invalid/generated.mp4"


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def byse_response() -> bytes:
    """Build a local versioned AES-GCM payload accepted by the maintained decoder."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = bytes(range(32))
    nonce = bytes(range(12))
    plaintext = json.dumps(
        {"sources": [{"url": MEDIA_URL, "height": 720}]},
        separators=(",", ":"),
    ).encode()
    encrypted = AESGCM(key).encrypt(nonce, plaintext, None)
    parts = [_b64url(bytes([index])) for index in range(30)]
    parts[0] = _b64url(key[:16])
    parts[29] = _b64url(key[16:])
    payload = {
        "playback": {
            "version": "1",
            "key_parts": parts,
            "iv": _b64url(nonce),
            "payload": _b64url(encrypted),
        }
    }
    return json.dumps(payload, separators=(",", ":")).encode()
