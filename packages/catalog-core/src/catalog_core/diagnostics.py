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
        "clone",
        "export_rows",
        "export_indexes",
        "export_summary",
        "validation_schema",
        "validation_integrity",
        "validation_relationships",
        "validation_rows",
        "validation_semantics",
        "validation_summary",
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
        "full_rebuild_required",
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
        "full export required": "full_rebuild_required",
    }.get(str(exc), "contract_rejected")


_records: list[dict] = []
REPORT_PREFIX = "catalog-diagnostic-"


def _report_target() -> str | None:
    """Only the supervisor's private temp report is writable via environment."""
    target = os.environ.get("ANIBRIDGE_CHILD_REPORT")
    if not target:
        return None
    path = Path(target)
    if path.name != "report.json" or not path.parent.name.startswith(REPORT_PREFIX):
        return None
    return target


def _save_report() -> None:
    target = _report_target()
    if target is None:
        return
    data = json.dumps(_records[-16:], separators=(",", ":")).encode("utf-8")
    try:
        descriptor = os.open(
            target,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        # Diagnostics must never turn a validation result into an I/O failure.
        pass


@contextmanager
def phase(name: str):
    if name not in PHASES:
        raise ValueError("unknown diagnostic phase")
    started = time.monotonic()
    record = {"phase": name, "reason": "ok", "duration_s": 0.0, "complete": False}
    _records.append(record)
    del _records[:-16]

    _save_report()
    try:
        yield
    except BaseException as exc:
        record["reason"] = reason(exc)
        raise
    finally:
        record.update(duration_s=round(time.monotonic() - started, 4), complete=True)
        _save_report()


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
    except OSError, ValueError, TypeError:
        return []
