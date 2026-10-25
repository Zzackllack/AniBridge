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
