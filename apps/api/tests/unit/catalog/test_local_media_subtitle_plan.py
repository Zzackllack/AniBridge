"""Local subtitle mapping and bounded probe checks; no network is used."""

import sys
from pathlib import Path

import pytest

from app.catalog import local_media_child
from app.catalog.local_media_child import subtitle_plan


@pytest.mark.parametrize(
    "codec",
    [
        "ass",
        "ssa",
        "subrip",
        "dvd_subtitle",
        "dvb_subtitle",
        "hdmv_pgs_subtitle",
        "arib_caption",
    ],
)
def test_matroska_compatible_text_and_bitmap_subtitles_are_copied(codec: str) -> None:
    maps, codecs = subtitle_plan(
        (({"index": 3, "codec_type": "subtitle", "codec_name": codec},),)
    )

    assert maps == ["-map", "0:3"]
    assert codecs == ["-c:s:0", "copy"]


@pytest.mark.parametrize("codec", ["mov_text", "webvtt"])
def test_text_subtitle_formats_use_srt_for_matroska(codec: str) -> None:
    maps, codecs = subtitle_plan(
        (({"index": 2, "codec_type": "subtitle", "codec_name": codec},),)
    )

    assert maps == ["-map", "0:2"]
    assert codecs == ["-c:s:0", "srt"]


def test_subtitle_plan_preserves_tracks_across_local_inputs() -> None:
    maps, codecs = subtitle_plan(
        (
            (
                {"index": 1, "codec_type": "audio", "codec_name": "aac"},
                {"index": 2, "codec_type": "subtitle", "codec_name": "subrip"},
            ),
            (
                {"index": 0, "codec_type": "subtitle", "codec_name": "webvtt"},
                {
                    "index": 1,
                    "codec_type": "subtitle",
                    "codec_name": "hdmv_pgs_subtitle",
                },
            ),
        )
    )

    assert maps == ["-map", "0:2", "-map", "1:0", "-map", "1:1"]
    assert codecs == ["-c:s:0", "copy", "-c:s:1", "srt", "-c:s:2", "copy"]


def test_unknown_subtitle_codec_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported subtitle codec"):
        subtitle_plan(
            (({"index": 4, "codec_type": "subtitle", "codec_name": "unknown"},),)
        )


def test_invalid_subtitle_stream_index_fails_closed() -> None:
    with pytest.raises(ValueError, match="invalid subtitle stream index"):
        subtitle_plan(
            (({"index": True, "codec_type": "subtitle", "codec_name": "subrip"},),)
        )


def test_probe_kills_child_when_metadata_exceeds_bound(tmp_path: Path) -> None:
    fake_probe = tmp_path / "fake-probe"
    fake_probe.write_text(
        f"#!{sys.executable}\nimport sys\nsys.stdout.write('x' * 70000)\n"
    )
    fake_probe.chmod(0o755)

    with pytest.raises(ValueError, match="metadata exceeds bound"):
        local_media_child._probe_streams(str(fake_probe), tmp_path / "input.mkv")


def test_probe_kills_child_when_metadata_does_not_arrive_before_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_probe = tmp_path / "fake-probe"
    fake_probe.write_text(
        f"#!{sys.executable}\nimport time\ntime.sleep(2)\nprint('{{\"streams\": []}}')\n"
    )
    fake_probe.chmod(0o755)
    monkeypatch.setattr(local_media_child, "PROBE_TIMEOUT_S", 0.05)

    with pytest.raises(ValueError, match="probe timed out"):
        local_media_child._probe_streams(str(fake_probe), tmp_path / "input.mkv")
