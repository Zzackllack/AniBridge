"""Local bounded operational events; never log response bodies or source URLs."""

import json
import logging
from datetime import datetime, timezone
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
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

    def child(
        self, provider: str, records: list[dict], exit_code=None, reason=None
    ) -> None:
        from catalog_core.diagnostics import PHASES, REASONS

        for row in records:
            if row["phase"] in PHASES and row["reason"] in REASONS:
                self.emit(provider, row["phase"], row["reason"], row["duration_s"])
        self.handler.handle(
            logging.LogRecord(
                "catalog_worker",
                logging.INFO,
                "",
                0,
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "provider": provider,
                        "stage": "child",
                        "exit_code": exit_code,
                        "reason": reason if reason in REASONS else "ok",
                    },
                    separators=(",", ":"),
                ),
                (),
                None,
            )
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
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "provider": provider,
                        "stage": "signal",
                        "coverage": status["coverage"],
                        "entries": status["entries"],
                        "overlaps": status["overlaps"],
                        "pending": status["pending"],
                        "unknown_languages": status["unknown_languages"],
                        "gap_since": status["gap_since"],
                        "gap_parents_pending": status["gap_parents_pending"],
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
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "stage": "storage",
                        **status,
                    },
                    separators=(",", ":"),
                ),
                (),
                None,
            )
        )

    def admission(self, provider: str, seconds: int) -> None:
        self.handler.handle(
            logging.LogRecord(
                "catalog_worker",
                logging.INFO,
                "",
                0,
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "provider": provider,
                        "stage": "admission",
                        "outcome": "local_budget_wait",
                        "wait_s": seconds,
                    },
                    separators=(",", ":"),
                ),
                (),
                None,
            )
        )

    def page(self, provider: str, ready, state) -> None:
        """Only counters and typed outcomes, never paths or exception messages."""
        meta = state.meta()
        work = state.db.execute(
            "SELECT due,failures FROM work WHERE path=?", (ready.plan.path,)
        ).fetchone()
        self.handler.handle(
            logging.LogRecord(
                "catalog_worker",
                logging.INFO,
                "",
                0,
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "provider": provider,
                        "stage": "page",
                        "outcome": ready.outcome,
                        "http_status": ready.status,
                        "error_class": ready.error_class,
                        "parser_reason": ready.parser_reason,
                        "child_exit": ready.child_exit,
                        "availability": ready.page.availability if ready.page else None,
                        "requests": ready.requests,
                        "network_s": round(ready.network_s, 4),
                        "parser_s": round(ready.parser_s, 4),
                        "admission_wait_s": ready.retry_after
                        if ready.outcome == "admission_deferred"
                        else 0,
                        "retry_due": work["due"]
                        if work and ready.outcome != "ok"
                        else None,
                        "attempts": work["failures"] if work else 0,
                        "retry_reason": ready.outcome
                        if ready.outcome != "ok"
                        else None,
                        "blocked_until": meta["blocked_until"],
                        "circuit_escalation": meta["block_count"],
                        "batch_rows": len(ready.page.episodes) if ready.page else 0,
                    },
                    separators=(",", ":"),
                ),
                (),
                None,
            )
        )

    def close(self) -> None:
        self.handler.close()
