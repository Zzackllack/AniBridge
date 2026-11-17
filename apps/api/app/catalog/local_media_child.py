"""Replace this limited process with local-only FFmpeg/ffprobe."""

import argparse
import json
import os
import resource
import select
import shutil
import subprocess
import time
from pathlib import Path

from catalog_core.supervisor import limit_child
from .media_tracks import validate_tracks_manifest

FORMATS = "mov,matroska,webm,mpegts"
FORMATS_WITH_CAPTIONS = f"{FORMATS},srt,webvtt"
LOCAL_MEMORY_BYTES = 320 * 1024**2
PROBE_BYTES = 65536
PROBE_TIMEOUT_S = 10
MAX_STREAMS = 64
COPY_SUBTITLE_CODECS = frozenset(
    {
        "ass",
        "ssa",
        "subrip",
        "dvd_subtitle",
        "dvb_subtitle",
        "hdmv_pgs_subtitle",
        "arib_caption",
    }
)
TEXT_SUBTITLE_CODECS = frozenset({"mov_text", "webvtt"})


def subtitle_plan(
    streams_by_input: tuple[tuple[dict, ...], ...],
) -> tuple[list[str], list[str]]:
    """Map supported embedded subtitle streams and choose a safe Matroska codec."""
    mappings, codecs = [], []
    for input_index, streams in enumerate(streams_by_input):
        for stream in streams:
            if type(stream) is not dict:
                raise ValueError("invalid subtitle stream metadata")
            if stream.get("codec_type") != "subtitle":
                continue
            codec = stream.get("codec_name")
            if (
                type(codec) is not str
                or codec not in COPY_SUBTITLE_CODECS | TEXT_SUBTITLE_CODECS
            ):
                raise ValueError("unsupported subtitle codec")
            stream_index = stream.get("index")
            if type(stream_index) is not int or stream_index < 0:
                raise ValueError("invalid subtitle stream index")
            output_index = len(codecs) // 2
            mappings.extend(("-map", f"{input_index}:{stream_index}"))
            codecs.extend(
                (
                    f"-c:s:{output_index}",
                    "srt" if codec in TEXT_SUBTITLE_CODECS else "copy",
                )
            )
    return mappings, codecs


def _probe_streams(binary: str, path: Path) -> tuple[dict, ...]:
    """Read bounded local stream metadata under this child and its deadline."""
    command = [
        binary,
        "-v",
        "error",
        "-probesize",
        "5000000",
        "-analyzeduration",
        "5000000",
        "-protocol_whitelist",
        "file,pipe",
        "-format_whitelist",
        FORMATS_WITH_CAPTIONS if path.suffix.lower() in {".srt", ".vtt"} else FORMATS,
        "-show_entries",
        "stream=index,codec_type,codec_name",
        "-of",
        "json",
        "-i",
        str(path.resolve()),
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert process.stdout is not None
        body = bytearray()
        deadline = time.monotonic() + PROBE_TIMEOUT_S
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError("local stream probe timed out")
            ready, _, _ = select.select([process.stdout], [], [], remaining)
            if not ready:
                raise ValueError("local stream probe timed out")
            block = os.read(
                process.stdout.fileno(), min(8192, PROBE_BYTES + 1 - len(body))
            )
            if not block:
                break
            body.extend(block)
            if len(body) > PROBE_BYTES:
                raise ValueError("stream metadata exceeds bound")
        try:
            status = process.wait(timeout=max(0.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise ValueError("local stream probe timed out") from None
        if status:
            raise ValueError("local stream probe failed")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if process.stdout is not None:
            process.stdout.close()

    try:
        decoded = json.loads(body)
        streams = decoded["streams"]
        if type(streams) is not list or len(streams) > MAX_STREAMS:
            raise ValueError("invalid stream metadata")
        result = []
        seen = set()
        for stream in streams:
            if type(stream) is not dict:
                raise ValueError("invalid stream metadata")
            index, kind, codec = (
                stream.get("index"),
                stream.get("codec_type"),
                stream.get("codec_name"),
            )
            if (
                type(index) is not int
                or index < 0
                or index in seen
                or kind not in {"video", "audio", "subtitle", "data", "attachment"}
                or type(codec) is not str
                or not 1 <= len(codec) <= 64
            ):
                raise ValueError("invalid stream metadata")
            seen.add(index)
            result.append({"index": index, "codec_type": kind, "codec_name": codec})
        return tuple(result)
    except KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError:
        raise ValueError("invalid stream metadata") from None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("probe", "remux"))
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--tracks-json", type=Path)
    args = parser.parse_args()
    # Native AMD64 remux/probe needs about 257 MiB of virtual mappings even
    # when sampled RSS is below 70 MiB. Keep a bounded 25% margin for these
    # native-only phases; parser/transfer children retain their 256-MiB cap.
    limit_child(memory_bytes=LOCAL_MEMORY_BYTES, output_bytes=resource.RLIM_INFINITY)
    resource.setrlimit(resource.RLIMIT_STACK, (1024**2, 1024**2))
    root = args.root.resolve()
    if args.tracks_json is None and not 1 <= len(args.inputs) <= 2:
        raise ValueError("invalid local input")
    if args.tracks_json is not None and args.operation != "remux":
        raise ValueError("track manifest is only valid for remux")
    if args.tracks_json is not None and len(args.inputs) > 16:
        raise ValueError("too many local inputs")
    if not all(
        path.resolve().is_relative_to(root) and path.is_file() for path in args.inputs
    ):
        raise ValueError("invalid local input")
    if not args.output.resolve().is_relative_to(root) or args.output.exists():
        raise ValueError("invalid local output")
    binary = shutil.which("ffprobe" if args.operation == "probe" else "ffmpeg")
    if binary is None:
        raise ValueError("local media tool unavailable")
    command = [binary, "-v", "error", "-threads", "1"]
    format_whitelist = FORMATS
    track_records = None
    if args.tracks_json is not None:
        track_records = validate_tracks_manifest(args.tracks_json, root, args.inputs)
        format_whitelist = FORMATS_WITH_CAPTIONS
    for path in args.inputs:
        # Also reject playlist/concat demuxers that could reference unrelated
        # local files. Only actual media containers may enter this phase.
        command += [
            "-protocol_whitelist",
            "file,pipe",
            "-format_whitelist",
            format_whitelist,
            "-i",
            str(path.resolve()),
        ]
    if args.operation == "probe":
        command += [
            "-show_entries",
            "stream=codec_type,codec_name,height,width:stream_tags=language:format=duration,size",
            "-of",
            "json",
            "-o",
            str(args.output),
        ]
    else:
        ffprobe_binary = shutil.which("ffprobe")
        if ffprobe_binary is None:
            raise ValueError("local stream probe unavailable")
        streams_by_input = tuple(
            _probe_streams(ffprobe_binary, path) for path in args.inputs
        )
        if sum(len(streams) for streams in streams_by_input) > MAX_STREAMS:
            raise ValueError("too many local media streams")
        if track_records is None:
            # Preserve the existing providers' one-video/optional-one-audio
            # remux path as-is.
            subtitle_maps, subtitle_codecs = subtitle_plan(streams_by_input)
            maps = [
                "-map",
                "0:v:0",
                "-map",
                "1:a:0" if len(args.inputs) == 2 else "0:a?",
            ]
            metadata = []
        else:
            subtitle_streams = tuple(
                streams
                if track_records[input_index]["kind"] in ("video", "subtitle")
                else ()
                for input_index, streams in enumerate(streams_by_input)
            )
            subtitle_maps, subtitle_codecs = subtitle_plan(subtitle_streams)
            video_input = next(
                index
                for index, record in enumerate(track_records)
                if record["kind"] == "video"
            )
            if not any(
                stream["codec_type"] == "video"
                for stream in streams_by_input[video_input]
            ):
                raise ValueError("video track has no video stream")
            has_separate_audio = any(
                record["kind"] == "audio" for record in track_records
            )
            maps = ["-map", f"{video_input}:v:0"]
            if not has_separate_audio:
                maps.extend(("-map", f"{video_input}:a?"))
            metadata = []
            output_audio_index = (
                0
                if has_separate_audio
                else sum(
                    stream["codec_type"] == "audio"
                    for stream in streams_by_input[video_input]
                )
            )
            for input_index, record in enumerate(track_records):
                if record["kind"] != "audio":
                    continue
                if not any(
                    stream["codec_type"] == "audio"
                    for stream in streams_by_input[input_index]
                ):
                    raise ValueError("audio track has no audio stream")
                maps.extend(("-map", f"{input_index}:a:0"))
                metadata.extend(
                    (
                        f"-metadata:s:a:{output_audio_index}",
                        f"language={record['language']}",
                    )
                )
                output_audio_index += 1

            for input_index, record in enumerate(track_records):
                if record["kind"] != "subtitle":
                    continue
                if not any(
                    stream["codec_type"] == "subtitle"
                    for stream in streams_by_input[input_index]
                ):
                    raise ValueError("subtitle track has no subtitle stream")

            output_subtitle_index = 0
            for input_index, streams in enumerate(subtitle_streams):
                record = track_records[input_index]
                for stream in streams:
                    if stream["codec_type"] != "subtitle":
                        continue
                    if record["kind"] == "subtitle":
                        metadata.extend(
                            (
                                f"-metadata:s:s:{output_subtitle_index}",
                                f"language={record['language']}",
                            )
                        )
                    output_subtitle_index += 1

        command += [
            *maps,
            *subtitle_maps,
            "-c",
            "copy",
            *subtitle_codecs,
            *metadata,
            # Stream copy needs no lookahead. Bound the producer/muxer queue so
            # fast local reads cannot fill the child address-space allowance.
            "-thread_queue_size",
            "1",
            "-f",
            "matroska",
            "-n",
            str(args.output),
        ]
    os.execv(binary, command)


if __name__ == "__main__":
    main()
