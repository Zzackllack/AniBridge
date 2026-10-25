"""Replace this limited process with local-only FFmpeg/ffprobe."""

import argparse
import os
import resource
import shutil
from pathlib import Path

from catalog_core.supervisor import limit_child

FORMATS = "mov,matroska,webm,mpegts"
LOCAL_MEMORY_BYTES = 320 * 1024**2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("probe", "remux"))
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("inputs", type=Path, nargs="+")
    args = parser.parse_args()
    # Native AMD64 remux/probe needs about 257 MiB of virtual mappings even
    # when sampled RSS is below 70 MiB. Keep a bounded 25% margin for these
    # native-only phases; parser/transfer children retain their 256-MiB cap.
    limit_child(memory_bytes=LOCAL_MEMORY_BYTES, output_bytes=resource.RLIM_INFINITY)
    resource.setrlimit(resource.RLIMIT_STACK, (1024**2, 1024**2))
    root = args.root.resolve()
    if not 1 <= len(args.inputs) <= 2 or not all(
        path.resolve().is_relative_to(root) and path.is_file() for path in args.inputs
    ):
        raise ValueError("invalid local input")
    if not args.output.resolve().is_relative_to(root) or args.output.exists():
        raise ValueError("invalid local output")
    binary = shutil.which("ffprobe" if args.operation == "probe" else "ffmpeg")
    if binary is None:
        raise ValueError("local media tool unavailable")
    command = [binary, "-v", "error", "-threads", "1"]
    for path in args.inputs:
        # Also reject playlist/concat demuxers that could reference unrelated
        # local files. Only actual media containers may enter this phase.
        command += [
            "-protocol_whitelist",
            "file,pipe",
            "-format_whitelist",
            FORMATS,
            "-i",
            str(path.resolve()),
        ]
    if args.operation == "probe":
        command += [
            "-show_entries",
            "stream=codec_type,codec_name,height,width:format=duration,size",
            "-of",
            "json",
            "-o",
            str(args.output),
        ]
    else:
        command += [
            "-map",
            "0:v:0",
            "-map",
            "1:a:0" if len(args.inputs) == 2 else "0:a?",
            "-c",
            "copy",
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
