"""Small atomic recovery receipt shared by canonical sources, outside ledgers."""

import math
import time
from contextlib import contextmanager
from pathlib import Path

from catalog_core.files import atomic_write
from catalog_core.json_codec import dumps, fields, integer, loads, require

FILENAME = "canonical-cooldowns.json"
LOCK_TIMEOUT_S = 2.0
ORIGINS = {
    "https://skyhook.sonarr.tv",
    "https://api.radarr.video",
    "https://api.themoviedb.org",
}


class CooldownWriteError(RuntimeError):
    """Stop collection when a source-wide recovery instruction cannot persist."""


def _read(filename: Path) -> dict[str, int]:
    """Parse one receipt; absence is empty and corruption refuses startup."""
    try:
        with filename.open("rb") as stream:
            raw = stream.read(4097)
    except FileNotFoundError:
        return {}
    data = fields(loads(raw, 4096), {"version", "until"})
    require(
        type(data["version"]) is int and data["version"] == 1,
        "invalid cooldown version",
    )
    values = fields(data["until"], set(), ORIGINS)
    return {origin: integer(until, 0, 253402300799) for origin, until in values.items()}


@contextmanager
def _writer(filename: Path):
    """Serialize read-modify-write across collector, backup and one-off commands.

    ``atomic_write`` only prevents a torn file. Two processes holding private
    snapshots could still erase each other's Retry-After; this lock makes the
    merge and replacement one critical section.
    """
    import fcntl

    lock = filename.with_name(filename.name + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as stream:
        deadline = time.monotonic() + LOCK_TIMEOUT_S
        while True:
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("canonical cooldown writer is busy") from None
                time.sleep(0.01)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class SourceCooldowns:
    def __init__(self, filename: Path | None = None) -> None:
        self.filename = filename
        self.until: dict[str, int] = {}
        if filename is not None:
            self.until = _read(filename)

    def refresh(self) -> None:
        """Observe another process's durable pause/clear before deciding."""
        if self.filename is not None:
            self.until = _read(self.filename)

    def delay(self, origin: str, now: float) -> int:
        self.refresh()
        return max(0, math.ceil(self.until.get(origin, 0) - now))

    def pause(self, origin: str, seconds: int, now: float) -> None:
        require(origin in ORIGINS, "unexpected canonical cooldown origin")
        if self.filename is None:
            self.until[origin] = max(
                self.until.get(origin, 0), math.ceil(now + max(1, min(86400, seconds)))
            )
            return
        try:
            with _writer(self.filename):
                # Reload under the lock: another process may have paused a
                # different origin after this instance was created.
                current = _read(self.filename)
                current[origin] = max(
                    current.get(origin, 0),
                    math.ceil(now + max(1, min(86400, seconds))),
                )
                atomic_write(self.filename, dumps({"version": 1, "until": current}))
                self.until = current
        except OSError as exc:
            # Per-title error handling must not turn this into a recoverable
            # lookup failure and continue after losing the shared receipt.
            raise CooldownWriteError(
                "cannot persist canonical source cooldown"
            ) from exc


def clear(filename: Path, origins: list[str]) -> int:
    """Operator override for a source wedged by a persisted Retry-After.

    A valid receipt is rewritten atomically; a corrupt receipt keeps refusing
    startup instead of being silently discarded.
    """
    require(
        bool(origins) and all(origin in ORIGINS for origin in origins),
        "unexpected canonical cooldown origin",
    )
    if not filename.exists():
        return 0
    with _writer(filename):
        receipt = SourceCooldowns(filename)
        removed = [origin for origin in origins if origin in receipt.until]
        if not removed:
            return 0
        for origin in removed:
            del receipt.until[origin]
        atomic_write(filename, dumps({"version": 1, "until": receipt.until}))
    return len(removed)
