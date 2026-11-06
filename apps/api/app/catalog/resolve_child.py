"""One bounded user-local metadata resolution, without transferring media."""

import logging
import os
import signal
import sys
from pathlib import Path

from catalog_core.files import atomic_write
from catalog_core.json_codec import dumps, loads
from catalog_core.supervisor import limit_child


def main() -> None:
    request_file, result_file, directory = map(Path, sys.argv[1:])
    limit_child()
    logging.disable(logging.CRITICAL)
    from loguru import logger

    logger.remove()
    os.environ["ANIWORLD_INSTALL_FOLDER"] = str(directory / "upstream")
    from .aniworld_resolution import resolve
    from .resolution_transport import Budget, ResolutionError

    def expired(*_) -> None:
        raise ResolutionError("transport_failure")

    signal.signal(signal.SIGALRM, expired)
    signal.alarm(60)
    request = loads(request_file.read_bytes(), 65536)
    budget = Budget()
    try:
        atomic_write(result_file, dumps({"phase": "resolving"}))
        media = resolve(
            request["payload"], request["origin"], tuple(request["hosts"]), budget
        )
        atomic_write(
            result_file,
            dumps(
                {
                    "phase": "finished",
                    "outcome": "ok",
                    "url": media.url,
                    "host": media.host,
                }
            ),
        )
    except ResolutionError as exc:
        atomic_write(result_file, dumps({"phase": "finished", "outcome": exc.code}))
    except Exception:  # noqa: BLE001 -- no raw extractor/token errors cross the child boundary
        atomic_write(
            result_file, dumps({"phase": "finished", "outcome": "extraction_error"})
        )
    finally:
        signal.alarm(0)
        budget.close()


if __name__ == "__main__":
    main()
