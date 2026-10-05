"""One isolated local resolution/transfer attempt; no database writes here."""

import argparse
import logging
import os
import resource
import signal
import time
import traceback
from pathlib import Path

from catalog_core.files import atomic_write
from catalog_core.json_codec import dumps, loads
from catalog_core.supervisor import limit_child


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument("status", type=Path)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    limit_child(output_bytes=resource.RLIM_INFINITY)
    logging.disable(logging.CRITICAL)
    from loguru import logger

    logger.disable("")
    logger.remove()
    request = loads(args.request.read_bytes(), 65536)
    # Mutable upstream state remains under the explicitly owned attempt folder.
    os.environ["ANIWORLD_INSTALL_FOLDER"] = str(args.directory / "upstream")
    from .aniworld_resolution import resolve
    from .media_download import transfer
    from .resolution_transport import Budget, ResolutionError

    def deadline(*_):
        raise ResolutionError("transport_failure")

    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(60)
    last_progress = 0.0

    def status(record: dict) -> None:
        atomic_write(args.status, dumps(record))

    def progress(record: dict) -> None:
        nonlocal last_progress
        now = time.monotonic()
        if now - last_progress >= 1:
            status({"phase": "downloading", "progress": record})
            last_progress = now

    budget = Budget()
    phase = "resolution"
    try:
        status({"phase": "resolving"})
        media = resolve(
            request["payload"], request["origin"], tuple(request["hosts"]), budget
        )
        signal.alarm(0)
        phase = "transfer"
        status({"phase": "downloading"})
        tracks = transfer(
            media.url, args.directory, progress, bandwidth=request.get("bandwidth")
        )
        status(
            {
                "phase": "finished",
                "outcome": "ok",
                "tracks": [str(path) for path in tracks],
                "host": media.host,
            }
        )
    except ResolutionError as exc:
        status(
            {
                "phase": "finished",
                "outcome": exc.code,
                "failed_stage": phase,
                "error_type": type(exc).__name__,
                "frames": [
                    frame.name
                    for frame in traceback.extract_tb(exc.__traceback__)[-12:]
                ],
            }
        )
    except Exception as exc:  # noqa: BLE001 -- keep third-party errors behind the private receipt
        # No exception strings: extractor errors can carry private media tokens.
        status(
            {
                "phase": "finished",
                "outcome": "extraction_error",
                "failed_stage": phase,
                "error_type": type(exc).__name__,
                "frames": [
                    frame.name
                    for frame in traceback.extract_tb(exc.__traceback__)[-12:]
                ],
            }
        )
    finally:
        budget.close()
        signal.alarm(0)


if __name__ == "__main__":
    main()
