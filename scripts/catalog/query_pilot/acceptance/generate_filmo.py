"""Generate a bounded, offline 720p multi-audio input for Filmo acceptance."""

from __future__ import annotations

import json
import os
import resource
import subprocess
from pathlib import Path


ROOT = Path("/generated")
TARGET = ROOT / "generated.mp4"
MAX_BYTES = 64 * 1024**2


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (110, 110))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_STACK, (1024**2, 1024**2))


def main() -> None:
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
    Path("/library").mkdir(parents=True, exist_ok=True)
    os.chown("/library", 1000, 1000)
    print(
        "generated one 6001-second 1280x720 test-pattern/tone MP4 offline; "
        "two audio tags, no embedded subtitles"
    )


if __name__ == "__main__":
    main()
