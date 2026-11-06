"""Keep publication history separate from current download-folder availability."""

from pathlib import Path


def missing_output(row: dict) -> bool:
    if row["status"] == "completed":
        return not row.get("result_path") or not Path(row["result_path"]).is_file()
    # Old recovery code rewrote completed records to this exact failure. Leave
    # their ledger/audit data intact; don't expose a stale import path or repeat
    # the transfer. Other failures and partial transfers keep their old meaning.
    return bool(
        row["status"] == "failed"
        and row.get("message") == "missing_output"
        and (row.get("progress") or 0) >= 100
        and row.get("result_path")
    )
