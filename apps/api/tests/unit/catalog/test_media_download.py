"""Synthetic byte streams only; these tests are not import/playback evidence."""

import httpx
import pytest

from app.catalog import media_transport
from app.catalog.media_download import transfer
from app.catalog.resolution_transport import ResolutionError


class Body(httpx.SyncByteStream):
    def __init__(self, content):
        self.content = content

    def __iter__(self):
        for position in range(0, len(self.content), 1024):
            yield self.content[position : position + 1024]


def fixture_transport(monkeypatch, pages):
    calls = []
    original = httpx.Client

    def fetch(request):
        calls.append(request)
        body = pages[request.url.path]
        return httpx.Response(
            200, headers={"Content-Length": str(len(body))}, stream=Body(body)
        )

    def client(**kwargs):
        return original(transport=httpx.MockTransport(fetch), **kwargs)

    monkeypatch.setattr(media_transport.httpx, "Client", client)
    monkeypatch.setattr(
        media_transport,
        "_validate_request_url",
        lambda url, **_: ("media.example", 443, "8.8.8.8"),
    )
    return calls


def test_progressive_transfer_streams_through_only_verified_handler(
    tmp_path, monkeypatch
):
    body = b"synthetic transport bytes" * 10000
    calls = fixture_transport(monkeypatch, {"/video": body})
    updates = []
    outputs = transfer("https://media.example/video", tmp_path, updates.append)
    assert len(outputs) == 1 and outputs[0].read_bytes() == body
    assert len(calls) >= 2
    assert all(
        call.url.host == "8.8.8.8" and call.headers["Host"] == "media.example"
        for call in calls
    )
    assert updates[-1]["downloaded_bytes"] == len(body)
    assert updates[-1]["total_bytes"] == len(body)
    assert any(0 < row["downloaded_bytes"] < row["total_bytes"] for row in updates)
    assert updates[-1]["total_bytes_estimated"] is False


def test_native_vod_segments_use_verified_transport_without_ffmpeg(
    tmp_path, monkeypatch
):
    from yt_dlp.downloader.external import FFmpegFD

    def forbidden(*args, **kwargs):
        pytest.fail("native transfer attempted an external network downloader")

    monkeypatch.setattr(FFmpegFD, "real_download", forbidden)
    segment = b"\x47" + b"\0" * 187
    manifest = b"#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXT-X-MEDIA-SEQUENCE:0\n#EXTINF:2,\nsegment.ts\n#EXT-X-ENDLIST\n"
    calls = fixture_transport(
        monkeypatch, {"/video.m3u8": manifest, "/segment.ts": segment}
    )
    outputs = transfer(
        "https://media.example/video.m3u8", tmp_path, lambda update: None
    )
    assert outputs[0].read_bytes() == segment
    assert any(call.url.path == "/segment.ts" for call in calls)


def test_non_vod_manifest_fails_without_external_fallback(tmp_path, monkeypatch):
    from yt_dlp.downloader.external import FFmpegFD

    monkeypatch.setattr(
        FFmpegFD, "real_download", lambda *a, **k: pytest.fail("external download")
    )
    manifest = b"#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2,\nsegment.ts\n"
    calls = fixture_transport(monkeypatch, {"/video.m3u8": manifest})
    with pytest.raises(ResolutionError, match="extraction_error"):
        transfer("https://media.example/video.m3u8", tmp_path, lambda update: None)
    assert all(call.url.path == "/video.m3u8" for call in calls)


def test_hls_supplies_estimated_intermediate_progress(tmp_path, monkeypatch):
    segment = b"\x47" + b"\0" * 131071
    manifest = (
        b"#EXTM3U\n#EXT-X-TARGETDURATION:2\n"
        + b"".join(f"#EXTINF:2,\npart-{i}.ts\n".encode() for i in range(4))
        + b"#EXT-X-ENDLIST\n"
    )
    fixture_transport(
        monkeypatch,
        {"/video.m3u8": manifest, **{f"/part-{i}.ts": segment for i in range(4)}},
    )
    updates = []
    outputs = transfer("https://media.example/video.m3u8", tmp_path, updates.append)
    assert outputs[0].stat().st_size == 4 * len(segment)
    assert any(
        row["total_bytes_estimated"]
        and 0 < row["downloaded_bytes"] < row["total_bytes"]
        for row in updates
    )
    assert updates[-1]["total_bytes"] == 4 * len(segment)
    assert updates[-1]["total_bytes_estimated"] is False


def _master_manifest(*, subtitles=False, codecs=True, same_language=False):
    lines = [
        "#EXTM3U",
        '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="Japanese",LANGUAGE="ja",DEFAULT=YES,AUTOSELECT=YES,URI="audio-ja.m3u8"',
        '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="English",LANGUAGE="en",DEFAULT=NO,AUTOSELECT=YES,URI="audio-en.m3u8"',
    ]
    if same_language:
        lines.append(
            '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="English Commentary",LANGUAGE="en",DEFAULT=NO,AUTOSELECT=YES,URI="audio-en-commentary.m3u8"'
        )
    if subtitles:
        lines.append(
            '#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="German",LANGUAGE="de",DEFAULT=NO,AUTOSELECT=YES,URI="subs-de.m3u8"'
        )
    lines.extend(
        [
            "#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=1280x720,"
            + ('CODECS="avc1.64001f,mp4a.40.2",' if codecs else "")
            + 'AUDIO="audio"'
            + (',SUBTITLES="subs"' if subtitles else ""),
            "video.m3u8",
        ]
    )
    return ("\n".join(lines) + "\n").encode()


def _audio_manifest(name):
    return f"#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2,\n{name}.ts\n#EXT-X-ENDLIST\n".encode()


def _filmo_selection(languages=("eng",)):
    return {
        "audio_languages": list(languages),
        "subtitle_languages": ["deu"],
        "subtitle_mode": "unknown",
    }


def test_filmo_hls_uses_declared_audio_language_not_highest_bitrate(
    tmp_path, monkeypatch
):
    pages = {
        "/master.m3u8": _master_manifest(),
        "/video.m3u8": _audio_manifest("video"),
        "/audio-en.m3u8": _audio_manifest("english"),
        "/audio-ja.m3u8": _audio_manifest("japanese"),
        "/video.ts": b"video-segment",
        "/english.ts": b"english-segment",
        "/japanese.ts": b"japanese-segment",
    }
    calls = fixture_transport(monkeypatch, pages)
    outputs = transfer(
        "https://media.example/master.m3u8",
        tmp_path,
        lambda update: None,
        selection=_filmo_selection(),
    )
    assert len(outputs) == 2
    paths = [call.url.path for call in calls]
    assert "/audio-en.m3u8" in paths
    assert "/english.ts" in paths
    assert "/audio-ja.m3u8" not in paths
    assert "/japanese.ts" not in paths


def test_filmo_hls_rejects_wrong_or_ambiguous_audio_before_media_download(
    tmp_path, monkeypatch
):
    pages = {
        "/master.m3u8": _master_manifest(),
        "/video.m3u8": _audio_manifest("video"),
    }
    calls = fixture_transport(monkeypatch, pages)
    with pytest.raises(ResolutionError, match="unsupported_media_tracks"):
        transfer(
            "https://media.example/master.m3u8",
            tmp_path,
            lambda update: None,
            selection=_filmo_selection(("ita",)),
        )
    assert all(call.url.path == "/master.m3u8" for call in calls)

    calls.clear()
    with pytest.raises(ResolutionError, match="unsupported_media_tracks"):
        transfer(
            "https://media.example/master.m3u8",
            tmp_path,
            lambda update: None,
            selection=_filmo_selection(("eng", "deu")),
        )
    assert all(call.url.path == "/master.m3u8" for call in calls)


def test_filmo_hls_rejects_unbound_or_duplicate_language_renditions(
    tmp_path, monkeypatch
):
    for manifest, extra in (
        (_master_manifest(codecs=False), {}),
        (
            _master_manifest(same_language=True),
            {"/audio-en-commentary.m3u8": _audio_manifest("commentary")},
        ),
    ):
        pages = {
            "/master.m3u8": manifest,
            "/video.m3u8": _audio_manifest("video"),
            **extra,
        }
        with monkeypatch.context() as scoped:
            calls = fixture_transport(scoped, pages)
            with pytest.raises(ResolutionError, match="unsupported_media_tracks"):
                transfer(
                    "https://media.example/master.m3u8",
                    tmp_path,
                    lambda update: None,
                    selection=_filmo_selection(),
                )
        assert all(call.url.path == "/master.m3u8" for call in calls)


def test_filmo_hls_external_captions_fail_closed(tmp_path, monkeypatch):
    calls = fixture_transport(
        monkeypatch,
        {
            "/master.m3u8": _master_manifest(subtitles=True),
            "/video.m3u8": _audio_manifest("video"),
        },
    )
    with pytest.raises(ResolutionError, match="unsupported_media_tracks"):
        transfer(
            "https://media.example/master.m3u8",
            tmp_path,
            lambda update: None,
            selection=_filmo_selection(),
        )
    assert all(call.url.path == "/master.m3u8" for call in calls)


def test_legacy_hls_keeps_highest_bitrate_audio_selection(tmp_path, monkeypatch):
    pages = {
        "/master.m3u8": _master_manifest(),
        "/video.m3u8": _audio_manifest("video"),
        "/audio-en.m3u8": _audio_manifest("english"),
        "/audio-ja.m3u8": _audio_manifest("japanese"),
        "/video.ts": b"video-segment",
        "/english.ts": b"english-segment",
        "/japanese.ts": b"japanese-segment",
    }
    calls = fixture_transport(monkeypatch, pages)
    outputs = transfer(
        "https://media.example/master.m3u8", tmp_path, lambda update: None
    )
    assert len(outputs) == 2
    paths = [call.url.path for call in calls]
    assert "/audio-ja.m3u8" in paths
    assert "/japanese.ts" in paths


def test_fractional_progress_crosses_strict_child_message_boundary():
    from app.catalog.media_download import progress_counters
    from catalog_core.json_codec import dumps, loads

    record = progress_counters(
        {"downloaded_bytes": 512, "speed": 1234.56, "eta": 2.5}, 100
    )
    assert loads(dumps(record)) == {
        "downloaded_bytes": 612,
        "total_bytes": None,
        "total_bytes_estimated": False,
        "speed": 1234,
        "eta": 2,
    }
    record = progress_counters({"speed": float("inf"), "eta": float("nan")})
    assert loads(dumps(record))["speed"] is None
