"""Generated HLS and local media fixtures for Filmo track preservation."""

import json
import shutil
import subprocess
import sys

import httpx
import pytest

from app.catalog import media_transport
from app.catalog.media_download import transfer
from app.catalog.media_tracks import validate_tracks_manifest
from app.catalog.executor import _filmo_output_tracks_present
from app.catalog.resolution_transport import ResolutionError


class Body(httpx.SyncByteStream):
    def __init__(self, content: bytes):
        self.content = content

    def __iter__(self):
        yield self.content


def _transport(monkeypatch, pages):
    calls = []
    original = httpx.Client

    def fetch(request):
        calls.append(request.url.path)
        body = pages[request.url.path]
        return httpx.Response(
            200, headers={"Content-Length": str(len(body))}, stream=Body(body)
        )

    monkeypatch.setattr(
        media_transport.httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(fetch), **kwargs),
    )
    monkeypatch.setattr(
        media_transport,
        "_validate_request_url",
        lambda url, **_: ("media.example", 443, "8.8.8.8"),
    )
    return calls


def _master(*, duplicate_english=False, subtitle_uri=None, codecs=True):
    rows = [
        '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="main",NAME="English",LANGUAGE="en",URI="audio-en.m3u8"',
        '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="main",NAME="Japanese",LANGUAGE="ja",URI="audio-ja.m3u8"',
        '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="fallback",NAME="English",LANGUAGE="en",URI="fallback-en.m3u8"',
    ]
    if duplicate_english:
        rows.append(
            '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="main",NAME="English Commentary",LANGUAGE="en",URI="audio-en-commentary.m3u8"'
        )
    if subtitle_uri is not None:
        rows.append(
            '#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="German",LANGUAGE="de",URI="'
            + subtitle_uri
            + '"'
        )
    rows += [
        "#EXT-X-STREAM-INF:BANDWIDTH=900000,RESOLUTION=1920x1080,"
        + ('CODECS="avc1.64001f,mp4a.40.2",' if codecs else "")
        + 'AUDIO="fallback"',
        "video-high.m3u8",
        "#EXT-X-STREAM-INF:BANDWIDTH=500000,RESOLUTION=1280x720,"
        + ('CODECS="avc1.64001f,mp4a.40.2",' if codecs else "")
        + 'AUDIO="main"'
        + (',SUBTITLES="subs"' if subtitle_uri is not None else ""),
        "video-main.m3u8",
    ]
    return ("#EXTM3U\n" + "\n".join(rows) + "\n").encode()


def _playlist(name):
    return f"#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2,\n{name}.ts\n#EXT-X-ENDLIST\n".encode()


def test_filmo_selects_every_declared_audio_using_stream_group_binding(
    tmp_path, monkeypatch
):
    calls = _transport(
        monkeypatch,
        {
            "/master.m3u8": _master(),
            "/video-high.m3u8": _playlist("video-high"),
            "/video-main.m3u8": _playlist("video-main"),
            "/audio-en.m3u8": _playlist("audio-en"),
            "/audio-ja.m3u8": _playlist("audio-ja"),
            "/video-main.ts": b"video",
            "/audio-en.ts": b"english",
            "/audio-ja.ts": b"japanese",
        },
    )
    outputs = transfer(
        "https://media.example/master.m3u8",
        tmp_path,
        lambda update: None,
        selection={"audio_languages": ["eng", "jpn"], "subtitle_languages": []},
    )

    assert len(outputs) == 3
    assert "/video-main.m3u8" in calls
    assert "/video-high.m3u8" not in calls
    assert "/audio-en.m3u8" in calls and "/audio-ja.m3u8" in calls
    manifest = json.loads((tmp_path / "tracks.json").read_text())
    assert manifest == {
        "version": 1,
        "tracks": [
            {
                "file": "track-0.partial-media",
                "kind": "video",
                "language": None,
                "format": None,
            },
            {
                "file": "track-1.partial-media",
                "kind": "audio",
                "language": "eng",
                "format": None,
            },
            {
                "file": "track-2.partial-media",
                "kind": "audio",
                "language": "jpn",
                "format": None,
            },
        ],
    }


def test_filmo_abstains_when_the_selected_audio_group_is_ambiguous(
    tmp_path, monkeypatch
):
    calls = _transport(
        monkeypatch,
        {"/master.m3u8": _master(duplicate_english=True)},
    )
    with pytest.raises(ResolutionError, match="unsupported_media_tracks"):
        transfer(
            "https://media.example/master.m3u8",
            tmp_path,
            lambda update: None,
            selection={"audio_languages": ["eng", "jpn"], "subtitle_languages": []},
        )
    assert set(calls) == {"/master.m3u8"}


def test_filmo_binds_audio_group_without_optional_codecs_attribute(
    tmp_path, monkeypatch
):
    calls = _transport(
        monkeypatch,
        {
            "/master.m3u8": _master(codecs=False),
            "/video-main.m3u8": _playlist("video-main"),
            "/audio-en.m3u8": _playlist("audio-en"),
            "/audio-ja.m3u8": _playlist("audio-ja"),
            "/video-main.ts": b"video",
            "/audio-en.ts": b"english",
            "/audio-ja.ts": b"japanese",
        },
    )
    outputs = transfer(
        "https://media.example/master.m3u8",
        tmp_path,
        lambda update: None,
        selection={"audio_languages": ["eng", "jpn"], "subtitle_languages": []},
    )
    assert len(outputs) == 3
    assert "/audio-en.m3u8" in calls and "/audio-ja.m3u8" in calls


def test_filmo_accepts_bounded_muxed_media_playlist_without_fake_audio_tags(
    tmp_path, monkeypatch
):
    calls = _transport(
        monkeypatch,
        {
            "/movie.m3u8": _playlist("muxed"),
            "/muxed.ts": b"generated muxed bytes",
        },
    )
    outputs = transfer(
        "https://media.example/movie.m3u8",
        tmp_path,
        lambda update: None,
        selection={
            "audio_languages": ["eng"],
            "subtitle_languages": ["deu"],
            "subtitle_mode": "unknown",
        },
    )
    assert len(outputs) == 1
    assert json.loads((tmp_path / "tracks.json").read_text())["tracks"] == [
        {"file": outputs[0].name, "kind": "video", "language": None, "format": None}
    ]
    assert "/muxed.ts" in calls


def test_filmo_muxed_leaf_requires_external_caption_when_mode_is_soft(
    tmp_path, monkeypatch
):
    calls = _transport(monkeypatch, {"/movie.m3u8": _playlist("muxed")})
    with pytest.raises(ResolutionError, match="unsupported_media_tracks"):
        transfer(
            "https://media.example/movie.m3u8",
            tmp_path,
            lambda update: None,
            selection={
                "audio_languages": ["eng"],
                "subtitle_languages": ["deu"],
                "subtitle_mode": "soft",
            },
        )
    assert "/muxed.ts" not in calls


def test_filmo_hls_vtt_subtitle_playlist_uses_native_bounded_transfer(
    tmp_path, monkeypatch
):
    subtitle = (
        b"#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2,\ncaption-segment.vtt\n"
        b"#EXT-X-ENDLIST\n"
    )
    calls = _transport(
        monkeypatch,
        {
            "/master.m3u8": _master(subtitle_uri="subs-de.m3u8"),
            "/video-main.m3u8": _playlist("video-main"),
            "/audio-en.m3u8": _playlist("audio-en"),
            "/audio-ja.m3u8": _playlist("audio-ja"),
            "/subs-de.m3u8": subtitle,
            "/video-main.ts": b"video",
            "/audio-en.ts": b"english",
            "/audio-ja.ts": b"japanese",
            "/caption-segment.vtt": (
                b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nGenerated\n"
            ),
        },
    )
    outputs = transfer(
        "https://media.example/master.m3u8",
        tmp_path,
        lambda update: None,
        selection={"audio_languages": ["eng", "jpn"], "subtitle_languages": ["deu"]},
    )
    assert len(outputs) == 4
    assert outputs[-1].suffix == ".vtt"
    assert b"Generated" in outputs[-1].read_bytes()
    assert "/caption-segment.vtt" in calls


def test_external_captions_satisfy_soft_language_when_hls_has_no_subtitle_group(
    tmp_path, monkeypatch
):
    from app.catalog.media_captions import CaptionTrack

    caption = b"1\n00:00:00,000 --> 00:00:01,000\nGenerated\n"
    calls = _transport(
        monkeypatch,
        {
            "/master.m3u8": _master(),
            "/video-main.m3u8": _playlist("video-main"),
            "/audio-en.m3u8": _playlist("audio-en"),
            "/audio-ja.m3u8": _playlist("audio-ja"),
            "/caption.srt": caption,
            "/video-main.ts": b"video",
            "/audio-en.ts": b"english",
            "/audio-ja.ts": b"japanese",
        },
    )
    outputs = transfer(
        "https://media.example/master.m3u8",
        tmp_path,
        lambda update: None,
        selection={
            "audio_languages": ["eng", "jpn"],
            "subtitle_languages": ["deu"],
            "subtitle_mode": "soft",
        },
        captions=(CaptionTrack("https://media.example/caption.srt", "deu", "srt"),),
    )
    assert len(outputs) == 4
    assert "/caption.srt" in calls


def test_track_manifest_rejects_symlink_and_input_mismatch(tmp_path):
    media = tmp_path / "track-0.partial-media"
    media.write_bytes(b"fixture")
    manifest = tmp_path / "tracks.json"
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "tracks": [
                    {
                        "file": media.name,
                        "kind": "video",
                        "language": None,
                        "format": None,
                    }
                ],
            }
        )
    )
    assert validate_tracks_manifest(manifest, tmp_path, [media])[0]["kind"] == "video"
    with pytest.raises(ValueError, match="invalid track inputs"):
        validate_tracks_manifest(manifest, tmp_path, [tmp_path / "other.mkv"])

    link = tmp_path / "track-link.mkv"
    link.symlink_to(media)
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "tracks": [
                    {
                        "file": link.name,
                        "kind": "video",
                        "language": None,
                        "format": None,
                    }
                ],
            }
        )
    )
    with pytest.raises(ValueError, match="invalid track inputs"):
        validate_tracks_manifest(manifest, tmp_path, [link])


def test_filmo_postprobe_requires_every_selected_track_language():
    payload = {
        "release_metadata": {
            "audio_languages": ["eng", "jpn"],
            "subtitle_languages": ["deu"],
            "subtitle_mode": "soft",
        }
    }
    records = (
        {"kind": "video", "language": None},
        {"kind": "audio", "language": "eng"},
        {"kind": "audio", "language": "jpn"},
        {"kind": "subtitle", "language": "deu"},
    )
    streams = [
        {"codec_type": "video"},
        {"codec_type": "audio", "tags": {"language": "eng"}},
        {"codec_type": "audio", "tags": {"language": "jpn"}},
        {"codec_type": "subtitle", "tags": {"language": "deu"}},
    ]
    assert _filmo_output_tracks_present(payload, records, {"streams": streams})
    assert not _filmo_output_tracks_present(
        payload, records[:-1], {"streams": streams[:-1]}
    )


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_byse_captions_use_verified_transfer_and_join_the_filmo_manifest(
    tmp_path, monkeypatch, newline
):
    from app.catalog.media_captions import CaptionTrack

    caption = newline.join(
        [b"1", b"00:00:00,000 --> 00:00:01,000", b"Generated caption", b""]
    )
    calls = _transport(
        monkeypatch,
        {"/movie.mp4": b"generated movie bytes", "/captions.srt": caption},
    )
    progress = []
    outputs = transfer(
        "https://media.example/movie.mp4",
        tmp_path,
        progress.append,
        selection={"audio_languages": ["eng"], "subtitle_languages": ["deu"]},
        captions=(CaptionTrack("https://media.example/captions.srt", "deu", "srt"),),
    )
    assert len(outputs) == 2
    assert outputs[1].read_text().endswith("Generated caption\n")
    assert "/captions.srt" in calls
    assert json.loads((tmp_path / "tracks.json").read_text())["tracks"][1] == {
        "file": outputs[1].name,
        "kind": "subtitle",
        "language": "deu",
        "format": "srt",
    }
    assert progress[-1]["downloaded_bytes"] == len(b"generated movie bytes") + len(
        caption
    )
    assert progress[-1]["total_bytes"] == progress[-1]["downloaded_bytes"]


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="native FFmpeg tools are required",
)
def test_generated_multiaudio_and_caption_inputs_keep_language_tags(
    tmp_path, monkeypatch
):
    video = tmp_path / "video.mkv"
    english = tmp_path / "audio-eng.m4a"
    japanese = tmp_path / "audio-jpn.m4a"
    subtitle = tmp_path / "caption-deu.srt"
    webvtt = tmp_path / "caption-eng.vtt"
    output = tmp_path / "verified.mkv"
    subtitle.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nGenerated caption\n",
        encoding="utf-8",
    )
    webvtt.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nGenerated WebVTT\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x180:r=24",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=220:sample_rate=48000",
            "-t",
            "2",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "mpeg4",
            "-c:a",
            "aac",
            "-metadata:s:a:0",
            "language=deu",
            "-y",
            str(video),
        ],
        check=True,
    )
    for path, frequency in ((english, "440"), (japanese, "660")):
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:sample_rate=48000",
                "-t",
                "2",
                "-c:a",
                "aac",
                "-y",
                str(path),
            ],
            check=True,
        )
    inputs = [video, english, japanese, subtitle, webvtt]
    track_manifest = tmp_path / "tracks.json"
    track_manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "tracks": [
                    {
                        "file": video.name,
                        "kind": "video",
                        "language": None,
                        "format": None,
                    },
                    {
                        "file": english.name,
                        "kind": "audio",
                        "language": "eng",
                        "format": None,
                    },
                    {
                        "file": japanese.name,
                        "kind": "audio",
                        "language": "jpn",
                        "format": None,
                    },
                    {
                        "file": subtitle.name,
                        "kind": "subtitle",
                        "language": "deu",
                        "format": "srt",
                    },
                    {
                        "file": webvtt.name,
                        "kind": "subtitle",
                        "language": "eng",
                        "format": "vtt",
                    },
                ],
            }
        )
    )

    from app.catalog import local_media_child

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "local_media_child",
            "remux",
            str(tmp_path),
            str(output),
            *map(str, inputs),
            "--tracks-json",
            str(track_manifest),
        ],
    )
    monkeypatch.setattr(local_media_child, "limit_child", lambda **kwargs: None)
    monkeypatch.setattr(local_media_child.resource, "setrlimit", lambda *args: None)
    monkeypatch.setattr(
        local_media_child.os,
        "execv",
        lambda binary, command: subprocess.run(command, check=True),
    )
    local_media_child.main()
    probe_path = tmp_path / "probe.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["local_media_child", "probe", str(tmp_path), str(probe_path), str(output)],
    )
    local_media_child.main()
    streams = json.loads(probe_path.read_text())["streams"]
    audio_languages = [
        stream.get("tags", {}).get("language")
        for stream in streams
        if stream["codec_type"] == "audio"
    ]
    subtitle_languages = [
        stream.get("tags", {}).get("language")
        for stream in streams
        if stream["codec_type"] == "subtitle"
    ]
    assert len(audio_languages) == 2
    assert set(audio_languages) == {"eng", "jpn"}
    assert set(subtitle_languages) == {"deu", "eng"}

    embedded_output = tmp_path / "embedded.mkv"
    embedded_manifest = tmp_path / "embedded-tracks.json"
    embedded_inputs = [video, subtitle]
    embedded_manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "tracks": [
                    {
                        "file": video.name,
                        "kind": "video",
                        "language": None,
                        "format": None,
                    },
                    {
                        "file": subtitle.name,
                        "kind": "subtitle",
                        "language": "deu",
                        "format": "srt",
                    },
                ],
            }
        )
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "local_media_child",
            "remux",
            str(tmp_path),
            str(embedded_output),
            *map(str, embedded_inputs),
            "--tracks-json",
            str(embedded_manifest),
        ],
    )
    local_media_child.main()
    embedded_probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type:stream_tags=language",
            "-of",
            "json",
            str(embedded_output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    embedded_streams = json.loads(embedded_probe.stdout)["streams"]
    embedded_languages = [
        stream.get("tags", {}).get("language")
        for stream in embedded_streams
        if stream["codec_type"] == "audio"
    ]
    assert embedded_languages == ["deu"]
