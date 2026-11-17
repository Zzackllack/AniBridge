"""Keep publication history separate from current download-folder availability."""

from pathlib import Path


def published_output(row: dict) -> bool:
    """Recognize completion, including the old missing-file recovery rewrite."""
    return row["status"] == "completed" or bool(
        row["status"] == "failed"
        and row.get("message") == "missing_output"
        and (row.get("progress") or 0) >= 100
        and row.get("result_path")
    )


def missing_output(row: dict) -> bool:
    # A moved/imported or expired source is unavailable for another import, but
    # its absence cannot undo verified publication or prove a client imported it.
    return published_output(row) and (
        not row.get("result_path") or not Path(row["result_path"]).is_file()
    )
