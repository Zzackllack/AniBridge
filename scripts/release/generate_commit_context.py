#!/usr/bin/env python3
"""
Generate commit context artifacts between two tags for release automation.

Outputs:
  - commit_context.json: structured commit metadata for downstream consumers
  - llm_release_context.md: human-readable summary for manual inspection
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable


def run_git_log(log_range: str) -> str:
    """Return raw git log output for the given range."""
    pretty = "%H%x00%h%x00%an%x00%ae%x00%cI%x00%s%x00%b%x1e"
    try:
        return subprocess.check_output(
            ["git", "log", "--reverse", f"--pretty=format:{pretty}", log_range],
            text=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - invocation failure
        raise SystemExit(f"git log failed for range '{log_range}': {exc}") from exc


def parse_log_output(raw_log: str) -> list[dict[str, object]]:
    """Convert git log output produced by run_git_log into structured entries."""
    entries: list[dict[str, object]] = []
    for chunk in raw_log.strip().split("\x1e"):
        if not chunk.strip():
            continue
        parts = chunk.split("\x00")
        if len(parts) != 7:
            continue
        commit, abbrev, author_name, author_email, authored_iso, subject, body = parts
        entries.append(
            {
                "commit": commit,
                "abbrev": abbrev,
                "subject": subject.strip(),
                "body": body.strip(),
                "author": {
                    "name": author_name.strip(),
                    "email": author_email.strip(),
                },
                "date": authored_iso.strip(),
            }
        )
    return entries


def format_markdown_summary(
    current_tag: str, previous_tag: str | None, entries: Iterable[dict[str, object]]
) -> str:
    """Render a Markdown summary for manual review."""
    lines: list[str] = [
        "# Release Commit Context",
        "",
        f"- Current tag: {current_tag}",
        f"- Previous tag: {previous_tag or '(none — initial release)'}",
    ]

    entries_list = list(entries)
    lines.append(f"- Commit count: {len(entries_list)}")

    if entries_list:
        lines.extend(("", "## Commits", ""))
        for entry in entries_list:
            subject = entry["subject"]
            abbrev = entry["abbrev"]
            author = entry["author"]
            date_iso = entry["date"]
            body = entry["body"]
            lines.append(f"- `{abbrev}` {subject}")
            lines.append(f"  Author: {author['name']} <{author['email']}>")
            lines.append(f"  Date: {date_iso}")
            if body:
                lines.append("  Message:")
                for body_line in str(body).splitlines():
                    lines.append(f"    {body_line}")
            lines.append("")
    else:
        lines.extend(("", "No commits found for the selected range."))

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-tag", required=True, help="Tag representing the release being prepared")
    parser.add_argument("--previous-tag", help="Most recent prior release tag (optional)")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to write artifacts into (defaults to current working directory)",
    )
    args = parser.parse_args(argv)

    current_tag: str = args.current_tag
    previous_tag: str | None = args.previous_tag or None
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    log_range = f"{previous_tag}..{current_tag}" if previous_tag else current_tag
    log_output = run_git_log(log_range)
    entries = parse_log_output(log_output)

    context = {
        "current_tag": current_tag,
        "previous_tag": previous_tag,
        "commit_count": len(entries),
        "commits": entries,
    }

    commit_json_path = output_dir / "commit_context.json"
    commit_json_path.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")

    markdown_summary = format_markdown_summary(current_tag, previous_tag, entries)
    summary_path = output_dir / "llm_release_context.md"
    summary_path.write_text(markdown_summary, encoding="utf-8")

    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution entry point
    sys.exit(main())
