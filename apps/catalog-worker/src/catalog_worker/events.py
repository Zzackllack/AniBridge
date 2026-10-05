"""Local bounded operational events; never log response bodies or source URLs."""

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class Events:
    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.handler = RotatingFileHandler(
            directory / "worker.jsonl",
            maxBytes=10 * 1024**2,
            backupCount=4,
            encoding="utf-8",
        )
        self.handler.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, provider: str, stage: str, outcome: str, duration: float) -> None:
        # Call sites supply only fixed outcomes or exception class names. Do not
        # add exception messages here: transport exceptions can contain tokens.
        message = json.dumps(
            {
                "provider": provider,
                "stage": stage,
                "outcome": outcome,
                "duration_s": round(duration, 3),
            },
            separators=(",", ":"),
        )
        self.handler.handle(
            logging.LogRecord("catalog_worker", logging.INFO, "", 0, message, (), None)
        )

    def signal(self, provider: str, status: dict, now: int) -> None:
        """Bounded counters only: do not add origin, paths or response values."""
        oldest = status["oldest_pending"]
        self.handler.handle(
            logging.LogRecord(
                "catalog_worker",
                logging.INFO,
                "",
                0,
                json.dumps(
                    {
                        "provider": provider,
                        "stage": "signal",
                        "coverage": status["coverage"],
                        "entries": status["entries"],
                        "overlaps": status["overlaps"],
                        "pending": status["pending"],
                        "unknown_languages": status["unknown_languages"],
                        "gap_since": status["gap_since"],
                        "checked_at": status["checked_at"],
                        "oldest_pending_age_s": None
                        if oldest is None
                        else max(0, now - oldest),
                    },
                    separators=(",", ":"),
                ),
                (),
                None,
            )
        )

    def storage(self, status: dict) -> None:
        # Keys come only from storage.status; no configured paths or secrets.
        self.handler.handle(
            logging.LogRecord(
                "catalog_worker",
                logging.INFO,
                "",
                0,
                json.dumps({"stage": "storage", **status}, separators=(",", ":")),
                (),
                None,
            )
        )

    def close(self) -> None:
        self.handler.close()
