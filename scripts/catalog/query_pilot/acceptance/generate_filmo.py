"""Generate a bounded, offline 720p multi-audio input for Filmo acceptance."""

from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
from pathlib import Path


ROOT = Path("/generated")
TARGET = ROOT / "generated.mp4"
MAX_BYTES = 64 * 1024**2
HLS_ROOT = ROOT / "hls"
HLS_MAX_BYTES = 128 * 1024**2


def _limits() -> None:
    # Two tagged AAC tracks span 100 minutes. Native ARM64 generation can use
    # more than 110 CPU seconds while staying below the 120-second wall limit.
    resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_STACK, (1024**2, 1024**2))


def generate_hls() -> None:
    if HLS_ROOT.exists():
        raise ValueError("acceptance requires a fresh generated-media volume")
    HLS_ROOT.mkdir()
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-threads",
            "1",
            "-i",
            str(TARGET),
            "-map",
            "0:a:0",
            "-map",
            "0:a:1",
            "-map",
            "0:v:0",
            "-c",
            "copy",
            "-f",
            "hls",
            "-hls_time",
            "60",
            "-hls_list_size",
            "0",
            "-hls_segment_filename",
            str(HLS_ROOT / "segment_%v_%04d.ts"),
            "-var_stream_map",
            "a:0,agroup:audio,default:yes,language:ENG "
            "a:1,agroup:audio,language:DEU "
            "v:0,agroup:audio",
            "-master_pl_name",
            "master.m3u8",
            "-n",
            str(HLS_ROOT / "stream_%v.m3u8"),
        ],
        check=True,
        timeout=120,
        preexec_fn=_limits,
        env={**os.environ, "MALLOC_ARENA_MAX": "1"},
    )

    master = (HLS_ROOT / "master.m3u8").read_text()
    audio_entries = [
        line
        for line in master.splitlines()
        if line.startswith("#EXT-X-MEDIA:TYPE=AUDIO")
    ]
    if len(audio_entries) != 2 or not any(
        'LANGUAGE="ENG"' in line and 'URI="stream_0.m3u8"' in line
        for line in audio_entries
    ):
        raise ValueError("generated HLS master must expose the English audio rendition")
    if not any(
        'LANGUAGE="DEU"' in line and 'URI="stream_1.m3u8"' in line
        for line in audio_entries
    ):
        raise ValueError("generated HLS master must expose the German audio rendition")
    for playlist, expected_type in (
        ("stream_0.m3u8", "audio"),
        ("stream_1.m3u8", "audio"),
        ("stream_2.m3u8", "video"),
    ):
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type:stream_tags=language:format=duration",
                "-of",
                "json",
                str(HLS_ROOT / playlist),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        probe = json.loads(result.stdout)
        streams = probe["streams"]
        if len(streams) != 1 or streams[0].get("codec_type") != expected_type:
            raise ValueError(
                f"generated {playlist} does not contain only {expected_type}"
            )
        if abs(float(probe["format"]["duration"]) - 6001) > 0.1:
            raise ValueError(f"generated {playlist} duration changed")

    segments = list(HLS_ROOT.glob("segment_*.ts"))
    if not all(
        any(path.name.startswith(f"segment_{index}_") for path in segments)
        for index in range(3)
    ):
        raise ValueError("generated HLS must contain video and both audio segment sets")
    if not 0 < sum(path.stat().st_size for path in segments) <= HLS_MAX_BYTES:
        raise ValueError("generated HLS segments exceeded their size bound")
    os.chown(HLS_ROOT, 1000, 1000)
    for path in [*HLS_ROOT.glob("*.m3u8"), *segments]:
        os.chown(path, 1000, 1000)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hls",
        action="store_true",
        help="also generate closed video and two-language audio HLS renditions",
    )
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    if TARGET.exists():
        raise ValueError("acceptance requires a fresh generated-media volume")
    # Both audio streams are tones. The language tags exercise metadata flow;
    # they do not represent spoken English or German.
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-filter_threads",
            "1",
            "-filter_complex_threads",
            "1",
            "-f",
            "lavfi",
            "-threads",
            "1",
            "-i",
            "smptebars=size=1280x720:rate=1",
            "-f",
            "lavfi",
            "-threads",
            "1",
            "-i",
            "sine=frequency=440:sample_rate=44100",
            "-f",
            "lavfi",
            "-threads",
            "1",
            "-i",
            "sine=frequency=660:sample_rate=44100",
            "-t",
            "6001",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-map",
            "2:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "38",
            "-threads",
            "1",
            "-c:a",
            "aac",
            "-b:a",
            "32k",
            "-metadata:s:a:0",
            "language=eng",
            "-metadata:s:a:0",
            "title=Generated English tone",
            "-metadata:s:a:1",
            "language=deu",
            "-metadata:s:a:1",
            "title=Generated German tone",
            "-movflags",
            "+faststart",
            "-fs",
            str(MAX_BYTES),
            "-n",
            str(TARGET),
        ],
        check=True,
        timeout=120,
        preexec_fn=_limits,
        env={**os.environ, "MALLOC_ARENA_MAX": "1"},
    )
    if not 0 < TARGET.stat().st_size <= MAX_BYTES:
        raise ValueError("generated media exceeded its size bound")
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height:stream_tags=language",
            "-of",
            "json",
            str(TARGET),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    observed = json.loads(probe.stdout)
    video = [
        stream for stream in observed["streams"] if stream.get("codec_type") == "video"
    ]
    audio = [
        stream for stream in observed["streams"] if stream.get("codec_type") == "audio"
    ]
    subtitles = [
        stream
        for stream in observed["streams"]
        if stream.get("codec_type") == "subtitle"
    ]
    duration = float(observed["format"]["duration"])
    if len(video) != 1 or (video[0].get("width"), video[0].get("height")) != (
        1280,
        720,
    ):
        raise ValueError("generated video is not the declared 1280x720 input")
    if len(audio) != 2 or duration != 6001:
        raise ValueError(
            "generated media must have two audio tracks and last exactly 6001 seconds"
        )
    if [stream.get("tags", {}).get("language") for stream in audio] != [
        "eng",
        "deu",
    ] or subtitles:
        raise ValueError(
            "input must contain tagged English/German audio and no subtitles"
        )
    os.chown(ROOT, 1000, 1000)
    os.chown(TARGET, 1000, 1000)
    if args.hls:
        generate_hls()
    Path("/library").mkdir(parents=True, exist_ok=True)
    os.chown("/library", 1000, 1000)
    print(
        "generated one 6001-second 1280x720 test-pattern/tone MP4 offline; "
        "two audio tags, no embedded subtitles"
        + (" and separated HLS video/audio renditions" if args.hls else "")
    )


if __name__ == "__main__":
    main()
