"""Finite server-only export, reused by the one-writer collection scheduler."""

import sys
import time
from pathlib import Path

from catalog_core.supervisor import limit_child

from .config import load
from .read_catalog import publish
from .state import State


def publish_config(path: Path) -> None:
    config = load(path)
    if set(config.providers) != {"aniworld.to"}:
        raise ValueError("AniWorld only in the first query pilot")
    state = State(config.state_dir / "aniworld.to.sqlite", "aniworld.to")
    try:
        publish(config, state, int(time.time()))
    finally:
        state.close()


if __name__ == "__main__":
    budget = limit_child(512 * 1024**2, 420)
    try:
        publish_config(Path(sys.argv[1]))
    finally:
        budget.close()
