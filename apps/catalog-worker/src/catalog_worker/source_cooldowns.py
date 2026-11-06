"""Small atomic recovery receipt shared by canonical sources, outside ledgers."""

import math
from pathlib import Path

from catalog_core.files import atomic_write
from catalog_core.json_codec import dumps, fields, integer, loads, require

FILENAME = "canonical-cooldowns.json"
ORIGINS = {
    "https://skyhook.sonarr.tv",
    "https://api.radarr.video",
    "https://api.themoviedb.org",
}


class CooldownWriteError(RuntimeError):
    """Stop collection when a source-wide recovery instruction cannot persist."""


class SourceCooldowns:
    def __init__(self, filename: Path | None = None) -> None:
        self.filename = filename
        self.until: dict[str, int] = {}
        if filename is not None:
            try:
                with filename.open("rb") as stream:
                    raw = stream.read(4097)
            except FileNotFoundError:
                return
            data = fields(loads(raw, 4096), {"version", "until"})
            require(
                type(data["version"]) is int and data["version"] == 1,
                "invalid cooldown version",
            )
            values = fields(data["until"], set(), ORIGINS)
            self.until = {
                origin: integer(until, 0, 253402300799)
                for origin, until in values.items()
            }

    def delay(self, origin: str, now: float) -> int:
        return max(0, math.ceil(self.until.get(origin, 0) - now))

    def pause(self, origin: str, seconds: int, now: float) -> None:
        require(origin in ORIGINS, "unexpected canonical cooldown origin")
        self.until[origin] = max(
            self.until.get(origin, 0), math.ceil(now + max(1, min(86400, seconds)))
        )
        if self.filename is not None:
            try:
                atomic_write(self.filename, dumps({"version": 1, "until": self.until}))
            except OSError as exc:
                # Per-title error handling must not turn this into a recoverable
                # lookup failure and continue after losing the shared receipt.
                raise CooldownWriteError(
                    "cannot persist canonical source cooldown"
                ) from exc
