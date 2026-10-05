"""Generated local media proof. No provider traffic or real *arr is involved."""

import asyncio
import json
import shutil
import subprocess
import sys

import pytest
from app.catalog.executor import SubprocessExecutor

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="Linux resource enforcement"
)


@pytest.mark.parametrize("dimensions", [(320, 180), (1280, 720), (1920, 1080)])
def test_generated_video_is_remuxed_and_probed_in_sequential_bounded_children(
    tmp_path, dimensions
):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("local FFmpeg tools unavailable")
    source = tmp_path / "generated.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={dimensions[0]}x{dimensions[1]}:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100",
            "-t",
            "2",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-c:a",
            "aac",
            str(source),
        ],
        check=True,
        timeout=30,
        capture_output=True,
    )
    executor = SubprocessExecutor({}, (), tmp_path)
    target, probe = tmp_path / "output.mkv", tmp_path / "probe.json"

    async def phases():
        assert (
            await executor._run(
                "app.catalog.local_media_child",
                ["remux", str(tmp_path), str(target), str(source)],
                activity=target,
            )
            == 0
        )
        assert (
            await executor._run(
                "app.catalog.local_media_child",
                ["probe", str(tmp_path), str(probe), str(target)],
                deadline=20,
            )
            == 0
        )

    asyncio.run(phases())
    data = json.loads(probe.read_text())
    video = next(
        stream for stream in data["streams"] if stream["codec_type"] == "video"
    )
    assert (
        video["height"] == dimensions[1]
        and video["width"] == dimensions[0]
        and video["codec_name"] == "h264"
    )
    assert float(data["format"]["duration"]) >= 2
    # Decode to the null muxer as a separate local playback/decodability check.
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(target),
            "-f",
            "null",
            "-",
        ],
        check=True,
        timeout=20,
        capture_output=True,
    )


def test_local_probe_rejects_playlist_references(tmp_path):
    if not shutil.which("ffprobe"):
        pytest.skip("local FFmpeg tools unavailable")
    source = tmp_path / "untrusted.txt"
    source.write_text("ffconcat version 1.0\nfile https://example.invalid/private\n")
    executor = SubprocessExecutor({}, (), tmp_path)
    code = asyncio.run(
        executor._run(
            "app.catalog.local_media_child",
            ["probe", str(tmp_path), str(tmp_path / "probe.json"), str(source)],
            deadline=20,
        )
    )
    assert code != 0


def test_executor_publishes_verified_generated_output(tmp_path):
    """Inject transfer bytes, then exercise the real remux/probe/publish phases."""
    from pathlib import Path
    from catalog_core.files import atomic_write
    from catalog_core.json_codec import dumps

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("local FFmpeg tools unavailable")
    source = tmp_path / "generated.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=10",
            "-t",
            "1",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            str(source),
        ],
        check=True,
        timeout=30,
        capture_output=True,
    )

    transfers = []

    class GeneratedTransfer(SubprocessExecutor):
        async def _run(self, module, arguments, **kwargs):
            if module == "app.catalog.job_child":
                transfers.append(True)
                # This deliberately proves only the downstream local phases.
                # Verified HTTP and provider extraction have separate tests.
                tracks = Path(arguments[2])
                tracks.mkdir()
                track = tracks / "generated.mp4"
                shutil.copyfile(source, track)
                atomic_write(
                    Path(arguments[1]),
                    dumps(
                        {
                            "phase": "finished",
                            "outcome": "ok",
                            "tracks": [str(track)],
                            "host": "VOE",
                        }
                    ),
                )
                return 0
            return await super()._run(module, arguments, **kwargs)

    downloads = tmp_path / "downloads"
    downloads.mkdir()
    executor = GeneratedTransfer(
        {"aniworld.to": "https://example.invalid"}, ("VOE",), downloads
    )
    updates = []
    payload = {
        "provider": "aniworld.to",
        "mode": "download",
        "save_path": str(downloads),
        "original_label": "Example.S01E01.German.Dub",
        "job_id": "a" * 32,
        "generation": 1,
    }
    result = asyncio.run(executor(payload, updates.append))
    assert result.code == "ok" and result.output.is_file()
    assert result.evidence["height"] == 180 and result.evidence["codec"] == "h264"
    assert result.output.name == "Example.S01E01.German.Dub.mkv"
    assert updates[-1]["downloaded_bytes"] == result.output.stat().st_size
    assert updates[-1]["total_bytes"] == result.output.stat().st_size
    assert not list(downloads.rglob("request.json"))
    assert list(downloads.rglob("probe.json"))
    # Simulate pause/restart after output publication but before durable completion.
    resumed = asyncio.run(executor({**payload, "generation": 3}, updates.append))
    assert resumed.code == "ok" and resumed.output == result.output
    assert len(transfers) == 1
    with result.output.open("ab") as stream:
        stream.write(b"changed after publication")
    rejected = asyncio.run(executor({**payload, "generation": 5}, updates.append))
    assert rejected.code == "output_conflict" and len(transfers) == 1


def test_generated_vod_transfer_can_be_remuxed(tmp_path, monkeypatch):
    from test_media_download import fixture_transport
    from app.catalog.media_download import transfer

    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg unavailable")
    source = tmp_path / "hls"
    source.mkdir()
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=10",
            "-t",
            "2",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-f",
            "hls",
            "-hls_playlist_type",
            "vod",
            str(source / "video.m3u8"),
        ],
        check=True,
        capture_output=True,
        timeout=20,
    )
    pages = {"/" + path.name: path.read_bytes() for path in source.iterdir()}
    fixture_transport(monkeypatch, pages)
    tracks = transfer(
        "https://media.example/video.m3u8", tmp_path / "tracks", lambda update: None
    )
    executor = SubprocessExecutor({}, (), tmp_path)
    assert (
        asyncio.run(
            executor._run(
                "app.catalog.local_media_child",
                [
                    "remux",
                    str(tmp_path),
                    str(tmp_path / "video.mkv"),
                    *map(str, tracks),
                ],
                deadline=20,
                diagnostic=tmp_path / "failure.json",
            )
        )
        == 0
    )
