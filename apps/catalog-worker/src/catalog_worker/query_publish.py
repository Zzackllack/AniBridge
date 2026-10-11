"""Finite server-only export, reused by the one-writer collection scheduler."""

import sys
import time
from pathlib import Path

from catalog_core.diagnostics import phase
from catalog_core.supervisor import limit_child

from .config import load
from .read_catalog import publish
from .state import State


def publish_config(path: Path, provider: str | None = None) -> None:
    config = load(path)
    for selected in [provider] if provider else config.providers:
        if selected not in config.providers:
            raise ValueError("provider unavailable")
        with phase("state_preflight"):
            state = State(config.state_dir / f"{selected}.sqlite", selected)
        try:
            publish(config, state, int(time.time()))
        finally:
            state.close()


if __name__ == "__main__":
    # File bytes and supervisor wall time are separate limits. Passing 420 as
    # the second positional argument capped SQLite files at 420 bytes.
    limit_child(memory_bytes=512 * 1024**2, output_bytes=1024**3)
    publish_config(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else None)
