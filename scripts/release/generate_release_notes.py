#!/usr/bin/env python3
"""
Generate release notes by calling the Gemini API with commit context.

Reads commit metadata from commit_context.json and writes formatted Markdown.
"""

from __future__ import annotations

import argparse
import json
import os
import textwrap
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_MODEL = "gemini-2.5-flash"
MAX_COMMITS_DEFAULT = 200


def sanitize(text: str, limit: int = 600) -> str:
    """Trim and cap long strings so prompts stay within practical bounds."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def build_prompt(repo_url: str, current_tag: str, previous_tag: str | None, commits: List[Dict[str, Any]]) -> str:
    """Compose the prompt for Gemini including normalized commit data."""
    normalized: List[Dict[str, Any]] = []
    for entry in commits:
        subject = sanitize(entry.get("subject", ""))
        body = sanitize(entry.get("body", ""))
        commit_hash = entry.get("commit", "")
        author = entry.get("author") or {}
        author_name = (author.get("name") or "").strip()
        url = f"{repo_url}/commit/{commit_hash}"
        normalized.append(
            {
                "subject": subject,
                "body": body,
                "author": author_name,  # Avoid sending email addresses to the LLM
                "date": entry.get("date", ""),
                "url": url,
            }
        )

    commit_json = json.dumps(normalized, indent=2)

    instructions = f"""
    Draft release notes for the AniBridge project.

    Repository: {repo_url}
    Current release tag: {current_tag}
    Previous release tag: {previous_tag or "none"}

    Follow this structure exactly:
    1. Start with a concise, single-paragraph summary (no heading) describing the overall release.
    2. Add a section titled "Breaking Changes". If there are none, write "Breaking Changes" followed by "None." on the next line.
    3. Add a section titled "New Features". If there are none, state that explicitly.
    4. Add a section titled "Other Changes". Include remaining noteworthy updates or say "None." if empty.

    Section formatting rules:
    - Use Markdown headings (`## Heading`) for "Breaking Changes", "New Features", and "Other Changes".
    - Inside each section, list items as bullet points.
    - Each bullet should cite the related commit using a Markdown link with the pattern `[short description](commit_url)`. Prefer the commit subject as the description.
    - When possible, group multiple commits from the same theme into a single bullet referencing multiple links.
    - Mention authors or additional context when the commit message alone is ambiguous.

    Commit data (JSON list of objects with subject, body, author, date, and url):
    {commit_json}
    """
    return textwrap.dedent(instructions).strip()


def call_gemini(api_key: str, model: str, prompt: str, timeout: int = 60) -> str:
    """Send request to Gemini API and return the generated text."""
    base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=f"{base_url}?key={api_key}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read()
    except urllib.error.URLError as exc:  # pragma: no cover - network failure handling
        raise SystemExit(f"Gemini API request failed: {exc}") from exc

    response_json = json.loads(response_body.decode("utf-8"))
    candidates = response_json.get("candidates") or []
    if not candidates:
        raise SystemExit(f"Gemini API returned no candidates: {response_json}")

    generated_text = ""
    for part in candidates[0].get("content", {}).get("parts") or []:
        if "text" in part:
            generated_text += part["text"]

    generated_text = generated_text.strip()
    if not generated_text:
        raise SystemExit("Gemini API returned empty release notes.")

    return generated_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-json", required=True, help="Path to commit_context.json produced earlier")
    parser.add_argument("--output", required=True, help="File path for the generated release notes markdown")
    parser.add_argument("--repo-url", default=None, help="Repository URL for commit links")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model identifier to use")
    parser.add_argument("--max-commits", type=int, default=MAX_COMMITS_DEFAULT, help="Maximum commits from context to include")
    args = parser.parse_args(argv)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY environment variable is required.")

    context_path = Path(args.context_json)
    if not context_path.is_file():
        raise SystemExit(f"Context file not found: {context_path}")

    context = json.loads(context_path.read_text(encoding="utf-8"))
    current_tag = context.get("current_tag")
    previous_tag = context.get("previous_tag")
    commits = context.get("commits", [])

    repo_url = args.repo_url or f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}".rstrip("/")
    model = args.model

    prompt = build_prompt(repo_url, current_tag, previous_tag, commits[: args.max_commits])
    generated_text = call_gemini(api_key, model, prompt)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generated_text + "\n", encoding="utf-8")

    summary_path_value = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path_value:
        Path(summary_path_value).write_text(
            "# Release Notes Preview\n\n" + generated_text + "\n",
            encoding="utf-8",
        )

    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())
