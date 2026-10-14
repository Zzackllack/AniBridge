"""Small typed child reports. Raw exceptions and stderr never cross this boundary."""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

PHASES = frozenset(
    {
        "state_preflight",
        "parse",
        "export",
        "validation",
        "publication_lock",
        "publication",
    }
)
REASONS = frozenset(
    {
        "ok",
        "contract_rejected",
        "validation_deadline",
        "sqlite_interrupted",
        "sqlite_error",
        "memory_limit",
        "file_limit",
        "io_error",
        "deadline",
        "child_exit",
        "child_signal",
        "unicode_error",
        "structure_changed",
        "access_interstitial",
        "video_section_missing",
        "metadata_incomplete",
        "parent_children_missing",
    }
)


def reason(exc: BaseException) -> str:
    if isinstance(exc, MemoryError):
        return "memory_limit"
    if isinstance(exc, UnicodeError):
        return "unicode_error"
    if isinstance(exc, TimeoutError):
        return "deadline"
    if isinstance(exc, sqlite3.Error):
        return (
            "sqlite_interrupted"
            if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_INTERRUPT
            else "sqlite_error"
        )
    if isinstance(exc, OSError):
        return "file_limit" if exc.errno == 27 else "io_error"
    # Only fixed parser/validator codes can leave the child. Never copy a URL,
    # exception text, language label or traceback into an operational report.
    return {
        "validation deadline": "validation_deadline",
        "access_interstitial": "access_interstitial",
        "video_section_missing": "video_section_missing",
        "metadata_incomplete": "metadata_incomplete",
        "structure_changed": "structure_changed",
        "parent_children_missing": "parent_children_missing",
    }.get(str(exc), "contract_rejected")


_records: list[dict] = []


@contextmanager
def phase(name: str):
    if name not in PHASES:
        raise ValueError("unknown diagnostic phase")
    started = time.monotonic()
    record = {"phase": name, "reason": "ok", "duration_s": 0.0, "complete": False}
    _records.append(record)
    del _records[:-16]

    def save():
        target = os.environ.get("ANIBRIDGE_CHILD_REPORT")
        if target:
            Path(target).write_text(json.dumps(_records[-16:], separators=(",", ":")))

    save()
    try:
        yield
    except BaseException as exc:
        record["reason"] = reason(exc)
        raise
    finally:
        record.update(duration_s=round(time.monotonic() - started, 4), complete=True)
        save()


def read_report(path: Path) -> list[dict]:
    try:
        with path.open("rb") as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            return []
        records = json.loads(raw)
        if not isinstance(records, list) or len(records) > 16:
            return []
        result = []
        for row in records:
            if (
                not isinstance(row, dict)
                or set(row) != {"phase", "reason", "duration_s", "complete"}
                or row["phase"] not in PHASES
                or row["reason"] not in REASONS
                or type(row["complete"]) is not bool
                or type(row["duration_s"]) not in (int, float)
                or not 0 <= row["duration_s"] <= 3600
            ):
                return []
            result.append(row)
        return result
    except (OSError, ValueError, TypeError):
        return []
