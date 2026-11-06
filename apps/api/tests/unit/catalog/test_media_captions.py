from pathlib import Path

import pytest

from app.catalog.media_captions import (
    CaptionTrack,
    acquire_captions,
    normalize_caption_language,
    validate_caption_text,
)
from app.catalog.resolution_transport import ResolutionError
from app.hosts.catalog_sources import UnsupportedMediaTracks, filemoon_playback


def _encrypted_byse_response(data, *, api_tracks=None):
    import base64
    import json

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key, iv = bytes(range(32)), bytes(range(12))

    def encode(value):
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    parts = [encode(bytes([index]) * 16) for index in range(30)]
    parts[0], parts[29] = encode(key[:16]), encode(key[16:])
    playback = {
        "version": "1",
        "algorithm": "AES-256-GCM",
        "key_parts": parts,
        "iv": encode(iv),
        "payload": encode(
            AESGCM(key).encrypt(
                iv, json.dumps(data, separators=(",", ":")).encode(), None
            )
        ),
    }
    result = {"playback": playback}
    if api_tracks is not None:
        result["tracks"] = api_tracks
    return json.dumps(result)


def test_byse_playback_exposes_only_recognized_private_caption_tracks():
    secret_url = "https://cdn.example/private-subtitle.vtt?token=secret"
    response = _encrypted_byse_response(
        {
            "sources": [{"url": "https://media.example/generated.mp4"}],
            "tracks": [
                {
                    "kind": "captions",
                    "file": secret_url,
                    "label": "German",
                }
            ],
        }
    )

    playback = filemoon_playback(response, allow_external_captions=True)

    assert playback is not None
    assert playback.source_url == "https://media.example/generated.mp4"
    assert playback.captions == (CaptionTrack(secret_url, "deu", "vtt"),)
    assert secret_url not in repr(playback)
    assert secret_url not in repr(playback.captions)


@pytest.mark.parametrize(
    "row,expected",
    [
        (
            {
                "kind": "captions",
                "file": "https://cdn.example/sub.vtt",
                "label": "German",
                "srclang": "de-DE",
                "default": True,
            },
            "deu",
        ),
        (
            {
                "kind": "captions",
                "file": "https://cdn.example/sub.vtt",
                "label": "Original",
                "srclang": "de-DE",
                "default": False,
            },
            "deu",
        ),
    ],
)
def test_byse_accepts_consistent_language_attributes_and_boolean_default(row, expected):
    response = _encrypted_byse_response(
        {
            "sources": [{"url": "https://media.example/generated.mp4"}],
            "tracks": [row],
        }
    )

    playback = filemoon_playback(response, allow_external_captions=True)

    assert playback is not None
    assert playback.captions[0].language == expected


@pytest.mark.parametrize(
    "row",
    [
        {
            "kind": "captions",
            "file": "https://cdn.example/sub.vtt",
            "label": "English",
            "lang": "de",
        },
        {
            "kind": "captions",
            "file": "https://cdn.example/sub.vtt",
            "label": "German",
            "srclang": "de-DE",
            "default": "true",
        },
        {
            "kind": "captions",
            "file": "https://cdn.example/sub.vtt",
            "label": "Original",
        },
    ],
)
def test_byse_rejects_conflicting_or_malformed_caption_language_attributes(row):
    response = _encrypted_byse_response(
        {
            "sources": [{"url": "https://media.example/generated.mp4"}],
            "tracks": [row],
        }
    )

    with pytest.raises(UnsupportedMediaTracks):
        filemoon_playback(response, allow_external_captions=True)


@pytest.mark.parametrize(
    "label,expected",
    [
        ("en-US", "eng"),
        ("en_US", "eng"),
        ("ja-JP", "jpn"),
        ("es-419", "spa"),
        ("ger", "deu"),
        ("xx-YY", None),
        ("unknown", None),
    ],
)
def test_caption_language_tags_normalize_without_unknown_fallback(label, expected):
    assert normalize_caption_language(label) == expected


@pytest.mark.parametrize(
    "track",
    [
        {"kind": "captions", "file": "https://cdn.example/sub.vtt", "label": "Unknown"},
        {"kind": "captions", "file": "https://cdn.example/sub.txt", "label": "German"},
        {"kind": "chapters", "file": "https://cdn.example/sub.vtt", "label": "German"},
        {"kind": "captions", "file": "http://cdn.example/sub.vtt", "label": "German"},
        {
            "kind": "captions",
            "file": "https://user:pass@cdn.example/sub.vtt",
            "label": "German",
        },
        {
            "kind": "captions",
            "file": "https://cdn.example/sub.vtt",
            "label": "German",
            "unknown": "x",
        },
    ],
)
def test_byse_playback_fails_closed_for_unknown_or_unsafe_caption_layouts(track):
    response = _encrypted_byse_response(
        {"sources": [{"url": "https://media.example/generated.mp4"}], "tracks": [track]}
    )

    with pytest.raises(UnsupportedMediaTracks):
        filemoon_playback(response, allow_external_captions=True)


class _Response:
    def __init__(self, body: bytes):
        self.body = body
        self.offset = 0
        self.headers = {"Content-Length": str(len(body))}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, size: int) -> bytes:
        value = self.body[self.offset : self.offset + size]
        self.offset += len(value)
        return value


class _YDL:
    def __init__(self, body: bytes):
        self.body = body
        self.urls = []

    def urlopen(self, url: str):
        self.urls.append(url)
        return _Response(self.body)


class _State:
    error = None

    def __init__(self, directory: Path):
        self.directory = directory

    def fail(self, code: str):
        self.error = code
        raise RuntimeError(code)


def test_caption_acquisition_uses_supplied_verified_client_and_returns_local_file(
    tmp_path,
):
    body = b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHallo\n"
    url = "https://cdn.example/secret.vtt?token=private"
    ydl = _YDL(body)
    updates = []

    files = acquire_captions(
        (CaptionTrack(url, "deu", "vtt"),),
        ydl,
        _State(tmp_path),
        tmp_path,
        updates.append,
    )

    assert ydl.urls == [url]
    assert files[0].path.name.startswith("caption-0-")
    assert files[0].path.suffix == ".vtt"
    assert files[0].language == "deu"
    assert files[0].format == "vtt"
    assert files[0].path.read_text() == body.decode()
    assert updates[-1]["status"] == "finished"
    assert all(url not in repr(update) for update in updates)


def test_srt_caption_acquisition_normalizes_line_endings(tmp_path):
    body = b"1\r\n00:00:01,000 --> 00:00:02,000\r\nHallo\r\n"
    files = acquire_captions(
        (CaptionTrack("https://cdn.example/private-subtitle.srt", "deu", "srt"),),
        _YDL(body),
        _State(tmp_path),
        tmp_path,
    )

    assert files[0].format == "srt"
    assert files[0].path.read_text() == "1\n00:00:01,000 --> 00:00:02,000\nHallo\n"


@pytest.mark.parametrize(
    "format,body",
    [
        ("vtt", b"WEBVTT\n\nnot a cue\n"),
        ("srt", b"1\nnot a timestamp\n"),
        ("vtt", b"<html>not captions</html>"),
        ("srt", b"\xff\xfe"),
    ],
)
def test_malformed_caption_text_is_rejected(format, body):
    with pytest.raises(ResolutionError, match="unsupported_media_tracks"):
        validate_caption_text(body, format)


def test_oversized_caption_removes_partial_files(tmp_path):
    from app.catalog.media_captions import MAX_CAPTION_BYTES

    body = b"WEBVTT\n" + (b"x" * MAX_CAPTION_BYTES)
    ydl = _YDL(body)
    track = CaptionTrack("https://cdn.example/large.vtt", "deu", "vtt")

    with pytest.raises(ResolutionError, match="unsupported_media_tracks"):
        acquire_captions((track,), ydl, _State(tmp_path), tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_truncated_caption_body_must_match_declared_content_length(tmp_path):
    body = b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n"
    ydl = _YDL(body)

    class TruncatedResponse(_Response):
        def __init__(self, content):
            super().__init__(content)
            self.headers["Content-Length"] = str(len(content) + 8)

    ydl.urlopen = lambda _url: TruncatedResponse(body)
    track = CaptionTrack("https://cdn.example/sub.vtt", "eng", "vtt")

    with pytest.raises(ResolutionError, match="transport_failure"):
        acquire_captions((track,), ydl, _State(tmp_path), tmp_path)

    assert list(tmp_path.iterdir()) == []
