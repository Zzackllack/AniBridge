"""Durable STRM creation after grab acceptance, with no media download."""

from pathlib import Path
from urllib.parse import urlsplit

from catalog_core.files import atomic_write
from catalog_core.json_codec import loads

from .async_database import call as database_call
from .output_publication import publish
from .output_receipt import fingerprint
from .runner import Outcome


async def create(
    payload: dict,
    request: Path,
    status: Path,
    attempt: Path,
    target: Path,
    receipt: Path,
    run,
    progress,
    mode: str,
) -> Outcome:
    if mode not in ("direct", "proxy"):
        return Outcome("extraction_error")
    code = await run(
        "app.catalog.resolve_child",
        [str(request), str(status), str(attempt)],
        status=status,
        deadline=60,
    )
    if code or not status.is_file() or status.stat().st_size > 65536:
        return Outcome("extraction_error")
    result = loads(status.read_bytes(), 65536)
    if result.get("outcome") != "ok":
        return Outcome(result.get("outcome", "extraction_error"))
    url = result.get("url")
    if (
        type(url) is not str
        or not 0 < len(url.encode()) <= 8192
        or any(c in url for c in "\r\n\0")
    ):
        return Outcome("extraction_error")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return Outcome("extraction_error")
    if mode == "proxy":
        from .strm_http import stream_url

        url = stream_url(payload["job_id"])
        parsed = urlsplit(url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            return Outcome("extraction_error")
    if target.exists() or target.is_symlink():
        return Outcome("output_conflict")
    staged = attempt / "verified.strm"
    atomic_write(staged, (url + "\n").encode())
    code = await run(
        "app.catalog.output_receipt",
        ["write", str(target.parent), str(staged), str(receipt), fingerprint(payload)],
        deadline=120,
    )
    if code:
        return Outcome("extraction_error")
    publish(staged, target)
    await database_call(
        progress,
        {
            "downloaded_bytes": target.stat().st_size,
            "total_bytes": target.stat().st_size,
        },
    )
    # Resolving a URL does not establish media height, codec, size or playback.
    return Outcome("ok", target)
