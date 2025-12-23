#!/usr/bin/env python3
"""
Generate release notes by calling the Gemini API with commit context.

Reads commit metadata from commit_context.json and writes formatted Markdown.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import textwrap
import traceback
from pathlib import Path
from typing import Any, Dict, List

from google import genai

DEFAULT_MODEL = "gemini-2.5-flash"
MAX_COMMITS_DEFAULT = 200
DEFAULT_LOG_LEVEL = "INFO"


def sanitize(text: str, limit: int = 600) -> str:
    """Trim and cap long strings so prompts stay within practical bounds."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def available_models(api_key: str) -> None:
    client = genai.Client(api_key=api_key)
    for m in client.models.list():
        print(getattr(m, "name", m))


def build_prompt(
    repo_url: str,
    current_tag: str,
    previous_tag: str | None,
    commits: List[Dict[str, Any]],
) -> str:
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


def call_gemini(api_key: str, model: str, prompt: str, logger: logging.Logger) -> str:
    """Send request to Gemini API and return the generated text."""
    logger.info("Initializing Gemini client.")
    try:
        client = genai.Client(api_key=api_key)
    except Exception as exc:
        logger.error("Failed to initialize Gemini client: %s", exc)
        logger.debug("Gemini client init traceback:\n%s", traceback.format_exc())
        raise

    logger.info(
        "Sending prompt to Gemini model '%s' (prompt chars=%s).", model, len(prompt)
    )
    try:
        response = client.models.generate_content(model=model, contents=prompt)
    except Exception as exc:
        logger.error("Gemini API request failed: %s", exc)
        logger.debug("Gemini request traceback:\n%s", traceback.format_exc())
        raise

    generated_text = (response.text or "").strip()
    if not generated_text:
        logger.error("Gemini API returned empty release notes.")
        logger.debug("Gemini response object: %r", response)
        raise ValueError("Gemini API returned empty release notes.")

    logger.info("Gemini API returned release notes (chars=%s).", len(generated_text))
    return generated_text


def configure_logging(log_level: str) -> logging.Logger:
    logger = logging.getLogger("anibridge.release_notes")
    logger.setLevel(log_level)

    handler = logging.StreamHandler()
    handler.setLevel(log_level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )

    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--context-json",
        required=True,
        help="Path to commit_context.json produced earlier",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="File path for the generated release notes markdown",
    )
    parser.add_argument(
        "--repo-url", default=None, help="Repository URL for commit links"
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help="Gemini model identifier to use"
    )
    parser.add_argument(
        "--max-commits",
        type=int,
        default=MAX_COMMITS_DEFAULT,
        help="Maximum commits from context to include",
    )
    parser.add_argument(
        "--log-level",
        default=DEFAULT_LOG_LEVEL,
        help="Logging level (e.g. DEBUG, INFO, WARNING)",
    )
    args = parser.parse_args(argv)

    logger = configure_logging(args.log_level.upper())
    logger.info("Starting release notes generation.")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable is required.")
        return 1

    context_path = Path(args.context_json)
    if not context_path.is_file():
        logger.error("Context file not found: %s", context_path)
        cwd = Path.cwd()
        fallback = cwd / "commit_context.json"
        if fallback.is_file():
            logger.error(
                "Found %s in %s. Did you mean --context-json %s?",
                fallback.name,
                cwd,
                fallback,
            )
        else:
            logger.error("No commit_context.json found in %s.", cwd)
        return 1

    try:
        context = json.loads(context_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse context JSON: %s", exc)
        logger.debug("Context JSON parse traceback:\n%s", traceback.format_exc())
        return 1
    except OSError as exc:
        logger.error("Failed to read context file: %s", exc)
        logger.debug("Context read traceback:\n%s", traceback.format_exc())
        return 1

    current_tag = context.get("current_tag")
    previous_tag = context.get("previous_tag")
    commits = context.get("commits", [])

    repo_url = (
        args.repo_url or f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}"
    )
    repo_url = repo_url.rstrip("/")
    if not repo_url or repo_url == "https://github.com":
        logger.warning("Repository URL is empty; commit URLs may be incomplete.")
    model = args.model

    if not current_tag:
        logger.warning(
            "Current tag missing from context; release notes may be less accurate."
        )
    if not commits:
        logger.warning("No commits found in context; release notes will be minimal.")

    logger.info(
        "Context loaded (current_tag=%s, previous_tag=%s, commits=%s).",
        current_tag,
        previous_tag,
        len(commits),
    )

    logger.debug("Using Gemini model: %s", model)
    logger.debug("Available models:")
    available_models(api_key)

    prompt = build_prompt(
        repo_url, current_tag, previous_tag, commits[: args.max_commits]
    )
    logger.debug("Prompt preview (first 400 chars): %s", prompt[:400])

    try:
        generated_text = call_gemini(api_key, model, prompt, logger)
    except Exception:
        logger.error("Release note generation failed.")
        return 1

    output_path = Path(args.output)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(generated_text + "\n", encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to write release notes to %s: %s", output_path, exc)
        logger.debug("Release notes write traceback:\n%s", traceback.format_exc())
        return 1

    logger.info("Release notes written to %s.", output_path)

    summary_path_value = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path_value:
        try:
            Path(summary_path_value).write_text(
                "# Release Notes Preview\n\n" + generated_text + "\n",
                encoding="utf-8",
            )
            logger.info("Step summary written to %s.", summary_path_value)
        except OSError as exc:
            logger.warning(
                "Failed to write step summary to %s: %s", summary_path_value, exc
            )

    logger.info("Release notes generation completed.")
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())
