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


def fixture_transport(
    monkeypatch,
    pages,
    *,
    head_fail_paths=(),
    head_partial_paths=(),
    head_content_range_paths=(),
):
    calls = []
    original = httpx.Client

    def fetch(request):
        calls.append(request)
        if request.method == "HEAD" and request.url.path in head_fail_paths:
            return httpx.Response(405)
        body = pages[request.url.path]
        headers = {"Content-Length": str(len(body))}
        status = 200
        if request.method == "HEAD" and request.url.path in head_partial_paths:
            status = 206
            headers["Content-Range"] = f"bytes 0-{len(body) - 1}/{len(body) * 2}"
        if request.method == "HEAD" and request.url.path in head_content_range_paths:
            headers["Content-Range"] = f"bytes 0-{len(body) - 1}/{len(body) * 2}"
        return httpx.Response(
            status,
            headers=headers,
            stream=Body(b"" if request.method == "HEAD" else body),
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
    assert not any(call.method == "HEAD" for call in calls)


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


def test_filmo_multitrack_preflight_estimates_total_before_audio_starts(
    tmp_path, monkeypatch
):
    video_segment = b"v" * 100
    audio_segment = b"a" * 40
    subtitle_segment = b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nSample subtitle\n"
    subtitle_manifest = _master_manifest(subtitles=True).replace(
        b'URI="subs-de.vtt"', b'URI="subs-de.m3u8"'
    )
    pages = {
        "/master.m3u8": subtitle_manifest,
        "/video.m3u8": _media_manifest("video", count=3),
        "/audio-en.m3u8": _media_manifest("english", count=3),
        "/subs-de.m3u8": _media_manifest("subs", count=3),
        "/video-0.ts": video_segment,
        "/video-1.ts": video_segment,
        "/video-2.ts": video_segment,
        "/english-0.ts": audio_segment,
        "/english-1.ts": audio_segment,
        "/english-2.ts": audio_segment,
        "/subs-0.ts": subtitle_segment,
        "/subs-1.ts": subtitle_segment,
        "/subs-2.ts": subtitle_segment,
    }
    calls = fixture_transport(monkeypatch, pages)
    updates = []
    selection = _filmo_selection()
    selection.update(subtitle_languages=["deu"], subtitle_mode="soft")

    transfer(
        "https://media.example/master.m3u8",
        tmp_path,
        updates.append,
        selection=selection,
    )

    pre_audio = [
        row for row in updates if 0 < row["downloaded_bytes"] < 3 * len(video_segment)
    ]
    assert pre_audio, "video progress must be reported before audio starts"
    expected = 3 * (len(video_segment) + len(audio_segment) + len(subtitle_segment))
    assert pre_audio[0]["total_bytes"] == expected
    assert all(row["total_bytes"] >= row["downloaded_bytes"] for row in pre_audio)
    assert all(row["total_bytes_estimated"] is True for row in pre_audio)
    assert sum(call.url.path == "/video.m3u8" for call in calls) == 1
    assert sum(call.url.path == "/audio-en.m3u8" for call in calls) == 1
    assert any(
        call.method == "HEAD" and call.url.path == "/video-0.ts" for call in calls
    )
    assert any(
        call.method == "HEAD" and call.url.path == "/english-0.ts" for call in calls
    )
    assert any(
        call.method == "HEAD" and call.url.path == "/subs-0.ts" for call in calls
    )


def test_failed_optional_head_keeps_transfer_usable_and_total_unknown(
    tmp_path, monkeypatch
):
    segment = b"segment-data" * 20
    pages = {
        "/master.m3u8": _master_manifest(),
        "/video.m3u8": _media_manifest("video", count=3),
        "/audio-en.m3u8": _media_manifest("english", count=3),
        "/video-0.ts": segment,
        "/video-1.ts": segment,
        "/video-2.ts": segment,
        "/english-0.ts": segment,
        "/english-1.ts": segment,
        "/english-2.ts": segment,
    }
    calls = fixture_transport(monkeypatch, pages, head_fail_paths=("/english-0.ts",))
    updates = []

    outputs = transfer(
        "https://media.example/master.m3u8",
        tmp_path,
        updates.append,
        selection=_filmo_selection(),
    )

    assert len(outputs) == 2
    first_track = [row for row in updates if row["downloaded_bytes"] < 3 * len(segment)]
    assert first_track and all(row["total_bytes"] is None for row in first_track)
    assert any(
        call.method == "GET" and call.url.path == "/video-0.ts" for call in calls
    )
    assert any(
        call.method == "GET" and call.url.path == "/english-0.ts" for call in calls
    )


@pytest.mark.parametrize(
    "head_options",
    [
        {"head_partial_paths": ("/english-0.ts",)},
        {"head_content_range_paths": ("/english-0.ts",)},
    ],
)
def test_partial_or_ranged_head_does_not_seed_a_track_total(
    tmp_path, monkeypatch, head_options
):
    segment = b"segment-data" * 20
    pages = {
        "/master.m3u8": _master_manifest(),
        "/video.m3u8": _media_manifest("video", count=3),
        "/audio-en.m3u8": _media_manifest("english", count=3),
        "/video-0.ts": segment,
        "/video-1.ts": segment,
        "/video-2.ts": segment,
        "/english-0.ts": segment,
        "/english-1.ts": segment,
        "/english-2.ts": segment,
    }
    calls = fixture_transport(monkeypatch, pages, **head_options)
    updates = []

    outputs = transfer(
        "https://media.example/master.m3u8",
        tmp_path,
        updates.append,
        selection=_filmo_selection(),
    )

    assert len(outputs) == 2
    first_track = [row for row in updates if row["downloaded_bytes"] < 3 * len(segment)]
    assert first_track and all(row["total_bytes"] is None for row in first_track)
    assert any(
        call.method == "GET" and call.url.path == "/english-0.ts" for call in calls
    )


def test_endlist_text_inside_segment_uri_does_not_mark_playlist_as_vod(
    tmp_path, monkeypatch
):
    manifest = (
        b"#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2,\nsegment.ts#EXT-X-ENDLIST\n"
    )
    calls = fixture_transport(
        monkeypatch, {"/video.m3u8": manifest, "/segment.ts": b"media-segment"}
    )

    with pytest.raises(ResolutionError, match="extraction_error"):
        transfer("https://media.example/video.m3u8", tmp_path, lambda update: None)

    assert not any(call.url.path == "/segment.ts" for call in calls)


def test_legacy_multitrack_hls_preflight_does_not_require_filmo_selection(
    tmp_path, monkeypatch
):
    video_segment = b"v" * 100
    japanese_segment = b"j" * 40
    master = _master_manifest().replace(
        b'CODECS="avc1.64001f,mp4a.40.2"', b'CODECS="avc1.64001f"'
    )
    pages = {
        "/master.m3u8": master,
        "/video.m3u8": _media_manifest("video", count=3),
        "/audio-ja.m3u8": _media_manifest("japanese", count=3),
        "/video-0.ts": video_segment,
        "/video-1.ts": video_segment,
        "/video-2.ts": video_segment,
        "/japanese-0.ts": japanese_segment,
        "/japanese-1.ts": japanese_segment,
        "/japanese-2.ts": japanese_segment,
    }
    calls = fixture_transport(monkeypatch, pages)
    updates = []

    transfer("https://media.example/master.m3u8", tmp_path, updates.append)

    pre_audio = [
        row for row in updates if 0 < row["downloaded_bytes"] < 3 * len(video_segment)
    ]
    assert pre_audio
    assert pre_audio[0]["total_bytes"] == 3 * (
        len(video_segment) + len(japanese_segment)
    )
    assert pre_audio[0]["total_bytes_estimated"] is True
    assert any(
        call.method == "HEAD" and call.url.path == "/japanese-0.ts" for call in calls
    )


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
            '#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="German",LANGUAGE="de",DEFAULT=NO,AUTOSELECT=YES,URI="subs-de.vtt"'
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


def _media_manifest(name, count):
    segments = "".join(f"#EXTINF:2,\n{name}-{index}.ts\n" for index in range(count))
    return f"#EXTM3U\n#EXT-X-TARGETDURATION:2\n{segments}#EXT-X-ENDLIST\n".encode()


def _filmo_selection(languages=("eng",)):
    return {
        "audio_languages": list(languages),
        "subtitle_languages": [],
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
    pages = {
        "/master.m3u8": _master_manifest(same_language=True),
        "/video.m3u8": _audio_manifest("video"),
        "/audio-en-commentary.m3u8": _audio_manifest("commentary"),
    }
    calls = fixture_transport(monkeypatch, pages)
    with pytest.raises(ResolutionError, match="unsupported_media_tracks"):
        transfer(
            "https://media.example/master.m3u8",
            tmp_path,
            lambda update: None,
            selection=_filmo_selection(),
        )
    assert all(call.url.path == "/master.m3u8" for call in calls)


def test_filmo_hls_downloads_declared_external_captions(tmp_path, monkeypatch):
    captions = b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nGenerated caption\n"
    calls = fixture_transport(
        monkeypatch,
        {
            "/master.m3u8": _master_manifest(subtitles=True),
            "/video.m3u8": _audio_manifest("video"),
            "/audio-en.m3u8": _audio_manifest("english"),
            "/subs-de.vtt": captions,
            "/video.ts": b"video",
            "/english.ts": b"english",
        },
    )
    outputs = transfer(
        "https://media.example/master.m3u8",
        tmp_path,
        lambda update: None,
        selection={**_filmo_selection(), "subtitle_languages": ["deu"]},
    )
    assert len(outputs) == 3
    assert outputs[-1].read_bytes() == captions
    manifest = (tmp_path / "tracks.json").read_text()
    assert '"kind":"subtitle","language":"deu","format":"vtt"' in manifest
    assert any(call.url.path == "/subs-de.vtt" for call in calls)


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
