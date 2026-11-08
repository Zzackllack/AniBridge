"""Supervise sequential transfer, remux and verification phases for a grab."""

import asyncio
from collections import Counter
import logging
import os
import signal
import sqlite3
import sys
import time
from pathlib import Path

from catalog_core.files import atomic_write
from catalog_core.json_codec import dumps, loads

from .async_database import call as database_call
from .output_paths import output_paths
from .output_publication import publish
from .output_receipt import fingerprint
from .quality_evidence import measured
from .runner import Outcome
from .media_tracks import validate_tracks_manifest

logger = logging.getLogger(__name__)


class SubprocessExecutor:
    def __init__(
        self,
        origins: dict[str, str],
        hosts: tuple[str, ...],
        download_root: Path,
        *,
        bandwidth: int | None = None,
        strm_mode: str = "direct",
    ) -> None:
        self.origins, self.hosts, self.bandwidth = dict(origins), hosts, bandwidth
        self.download_root = download_root.resolve()
        self.strm_mode = strm_mode

    async def _run(
        self,
        module: str,
        arguments: list[str],
        *,
        status: Path | None = None,
        progress=None,
        deadline: float | None = None,
        activity: Path | None = None,
        diagnostic: Path | None = None,
        job_id: str | None = None,
    ) -> int:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            module,
            *arguments,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
            # Upstream parser imports start pool-maintenance threads. glibc's
            # per-thread arena reservations otherwise exhaust RLIMIT_AS before
            # any media work. Limit arenas, keeping the 256-MiB cap unchanged.
            env={
                **os.environ,
                "MALLOC_ARENA_MAX": "1",
                "ANIBRIDGE_SUPERVISOR_PID": str(os.getpid()),
            },
        )
        started = changed_at = time.monotonic()
        previous = None
        previous_progress = None
        previous_phase = None
        timeout_reason = None
        parent_failure = None
        operation = "supervision"
        observed_bytes = None
        progress_storage_busy = False

        async def read_output(stream) -> bytes:
            collected = bytearray()
            while block := await stream.read(4096):
                collected.extend(block)
                if len(collected) > 65536:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    return b"diagnostic_limit"
            return bytes(collected)

        errors = asyncio.create_task(read_output(process.stderr))
        output = asyncio.create_task(read_output(process.stdout))
        try:
            while process.returncode is None:
                now = time.monotonic()
                if deadline is not None and now - started > deadline:
                    timeout_reason = "phase_deadline"
                    raise TimeoutError("local media phase deadline")
                if status and status.exists():
                    operation = "status_read"
                    if status.stat().st_size > 65536:
                        raise ValueError("invalid child status")
                    record = loads(status.read_bytes(), 65536)
                    if record.get("phase") == "resolving" and now - started > 60:
                        timeout_reason = "resolution_deadline"
                        raise TimeoutError("resolution deadline")
                    if record.get("phase") != previous_phase:
                        previous_phase, changed_at = record.get("phase"), now
                    update = record.get("progress")
                    if update and update.get("downloaded_bytes") != observed_bytes:
                        observed_bytes = update.get("downloaded_bytes")
                        changed_at = now
                    if progress and update and update != previous_progress:
                        operation = "progress_write"
                        try:
                            await database_call(progress, update)
                        except sqlite3.OperationalError as exc:
                            if not _sqlite_busy(exc):
                                raise
                            # Progress is a replaceable snapshot. Keep the child
                            # running and retry the latest snapshot next poll.
                            if not progress_storage_busy:
                                logger.warning(
                                    "catalog progress persistence delayed job_id=%s "
                                    "reason=database_busy; transfer continues",
                                    job_id,
                                )
                            progress_storage_busy = True
                        else:
                            if progress_storage_busy:
                                logger.info(
                                    "catalog progress persistence recovered job_id=%s",
                                    job_id,
                                )
                            progress_storage_busy = False
                            previous_progress = update
                    if previous_phase == "downloading" and now - changed_at > 120:
                        timeout_reason = "download_inactivity"
                        raise TimeoutError("download inactivity")
                elif status and now - started > 60:
                    timeout_reason = "startup_deadline"
                    raise TimeoutError("resolution startup deadline")
                if activity:
                    size = activity.stat().st_size if activity.exists() else 0
                    if size != previous:
                        previous, changed_at = size, now
                    if now - changed_at > 120:
                        timeout_reason = "media_stall"
                        raise TimeoutError("local media phase stalled")
                try:
                    operation = "supervision"
                    await asyncio.wait_for(process.wait(), 0.2)
                except TimeoutError:
                    pass
            detail, stdout = await asyncio.gather(errors, output)
            code = process.returncode
            if detail == b"diagnostic_limit" or stdout == b"diagnostic_limit":
                code, detail = -1, b"diagnostic_limit"
            if code and diagnostic:
                reason = _stderr_failure_reason(detail, module.rsplit(".", 1)[-1])
                error_class = (
                    "output_limit" if detail == b"diagnostic_limit" else "process_exit"
                )
                _write_failure_diagnostic(
                    diagnostic,
                    module,
                    error_class,
                    reason,
                    process.returncode,
                    job_id,
                )
            return code
        except Exception as exc:
            # Preserve the class and operation, never the exception's message:
            # callback/storage failures can otherwise become an unexplained
            # extraction_error while the saved child phase still says downloading.
            if not timeout_reason:
                parent_failure = (type(exc).__name__, operation + "_failed")
            raise
        finally:
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await asyncio.wait_for(asyncio.shield(process.wait()), 2)
            await asyncio.gather(errors, output, return_exceptions=True)
            if timeout_reason and diagnostic:
                _write_failure_diagnostic(
                    diagnostic,
                    module,
                    "timeout",
                    timeout_reason,
                    process.returncode,
                    job_id,
                )
            elif parent_failure and diagnostic:
                _write_failure_diagnostic(
                    diagnostic,
                    module,
                    *parent_failure,
                    process.returncode,
                    job_id,
                )

    async def __call__(self, payload: dict, progress) -> Outcome:
        if sys.platform != "linux":
            return Outcome("native_enforcement_unavailable")
        if payload.get("mode") not in ("download", "strm"):
            return Outcome("extraction_error")
        if payload.get("legacy") and not payload.get("path"):
            return Outcome("legacy_request_incomplete")
        origin = self.origins.get(payload["provider"])
        if origin is None:
            return Outcome("disabled_provider")
        # Paths come from durable admission, but containment is checked again
        # before writing. Each attempt keeps separate partials; no unsafe resume
        # against a potentially changed signed URL or representation.
        parent = Path(payload["save_path"]).resolve()
        if not parent.is_relative_to(self.download_root):
            return Outcome("invalid_output_path")
        root, target = output_paths(payload, payload["job_id"])
        if root.is_symlink() or not root.resolve().is_relative_to(parent):
            return Outcome("invalid_output_path")
        receipt = root / ".verified-output.json"
        if target.exists() or target.is_symlink():
            # Pause can win the job CAS after verified publication. Reuse only
            # bytes bound to this frozen request; never overwrite an arbitrary file.
            try:
                code = await self._run(
                    "app.catalog.output_receipt",
                    [
                        "verify",
                        str(root),
                        str(target),
                        str(receipt),
                        fingerprint(payload),
                    ],
                    deadline=120,
                )
                if code:
                    return Outcome("output_conflict")
                await _published_progress(progress, target, payload["job_id"])
                return Outcome("ok", target)
            except OSError, ValueError, TimeoutError:
                return Outcome("output_conflict")
        attempt = root / f".attempt-{int(payload['generation'])}"
        attempt.mkdir(parents=True, exist_ok=False)
        request, status = attempt / "request.json", attempt / "status.json"
        atomic_write(
            request,
            dumps(
                {
                    "payload": payload,
                    "origin": origin,
                    "hosts": payload.get("host_preference")
                    if payload.get("host_preference") is not None
                    else list(self.hosts),
                    "bandwidth": self.bandwidth,
                }
            ),
        )
        try:
            if payload["mode"] == "strm":
                from .strm_output import create

                return await create(
                    payload,
                    request,
                    status,
                    attempt,
                    target,
                    receipt,
                    self._run,
                    progress,
                    payload.get("strm_delivery", "direct"),
                )
            code = await self._run(
                "app.catalog.job_child",
                [str(request), str(status), str(attempt / "tracks")],
                status=status,
                progress=progress,
                diagnostic=attempt / "failure.json",
                job_id=payload["job_id"],
            )
            if code or not status.is_file():
                atomic_write(
                    status,
                    dumps(
                        {
                            "phase": "finished",
                            "outcome": "extraction_error",
                            "child_exit_code": code,
                        }
                    ),
                )
                return Outcome("extraction_error")
            result = loads(status.read_bytes(), 65536)
            if result.get("outcome") != "ok":
                return Outcome(result.get("outcome", "extraction_error"))
            raw_tracks = result.get("tracks")
            if type(raw_tracks) is not list or any(
                type(path) is not str for path in raw_tracks
            ):
                return Outcome("extraction_error")
            tracks = [Path(path) for path in raw_tracks]
            filmo = payload.get("provider") == "filmo.to"
            track_manifest = attempt / "tracks" / "tracks.json"
            filmo_tracks = None
            if filmo:
                try:
                    filmo_tracks = validate_tracks_manifest(
                        track_manifest, attempt, tracks
                    )
                except OSError, TypeError, ValueError:
                    return Outcome("extraction_error")
            elif not 1 <= len(tracks) <= 2 or not all(
                path.is_file() and path.resolve().is_relative_to(attempt)
                for path in tracks
            ):
                return Outcome("extraction_error")
            remux = attempt / "verified.mkv"
            remux_args = ["remux", str(attempt), str(remux), *map(str, tracks)]
            if filmo:
                remux_args.extend(("--tracks-json", str(track_manifest)))
            code = await self._run(
                "app.catalog.local_media_child",
                remux_args,
                activity=remux,
                diagnostic=attempt / "failure.json",
            )
            if code:
                return Outcome("extraction_error")
            probe = attempt / "probe.json"
            code = await self._run(
                "app.catalog.local_media_child",
                ["probe", str(attempt), str(probe), str(remux)],
                deadline=20,
                diagnostic=attempt / "failure.json",
            )
            if code or not probe.is_file() or probe.stat().st_size > 65536:
                return Outcome("extraction_error")
            inspected = loads(probe.read_bytes(), 65536)
            if not any(
                stream.get("codec_type") == "video"
                for stream in inspected.get("streams", [])
            ):
                return Outcome("extraction_error")
            if float(inspected.get("format", {}).get("duration", 0)) <= 0:
                return Outcome("extraction_error")
            if filmo and not _filmo_output_tracks_present(
                payload, filmo_tracks, inspected
            ):
                return Outcome("extraction_error")
            if target.exists():
                return Outcome("output_conflict")
            code = await self._run(
                "app.catalog.output_receipt",
                ["write", str(root), str(remux), str(receipt), fingerprint(payload)],
                deadline=120,
            )
            if code:
                return Outcome("extraction_error")
            with remux.open("rb") as stream:
                os.fsync(stream.fileno())
            publish(remux, target)
            await _published_progress(progress, target, payload["job_id"])
            evidence = (
                measured(inspected, result["host"])
                if type(result.get("host")) is str
                else None
            )
            return Outcome("ok", target, evidence)
        except ValueError, OSError, TimeoutError:
            return Outcome("extraction_error")
        finally:
            request.unlink(missing_ok=True)


async def _published_progress(progress, target: Path, job_id: str) -> None:
    try:
        size = target.stat().st_size
        await database_call(progress, {"downloaded_bytes": size, "total_bytes": size})
    except sqlite3.OperationalError as exc:
        if not _sqlite_busy(exc):
            raise
        # Jobs.finish records exact bytes in its completion transaction. A
        # replaceable checkpoint must not reclassify verified output as failed.
        logger.warning(
            "catalog published progress delayed job_id=%s reason=database_busy; "
            "completion will record exact bytes",
            job_id,
        )


def _stderr_failure_reason(detail: bytes, module_stage: str) -> str:
    # Child stderr may contain URLs, local paths, release titles, or credentials.
    # Map only known markers to stable labels and discard the original bytes.
    classes = {
        b"Cannot allocate memory": "memory_limit",
        b"not on whitelist": "unsupported_container",
        b"Invalid data found": "invalid_media",
        b"matches no streams": "missing_stream",
        b"Timestamps are unset": "missing_timestamps",
        b"diagnostic_limit": "diagnostic_limit",
    }
    default = (
        "media_process_failed"
        if module_stage == "local_media_child"
        else "child_process_failed"
    )
    return next(
        (value for marker, value in classes.items() if marker in detail), default
    )


def _sqlite_busy(exc: sqlite3.OperationalError) -> bool:
    code = getattr(exc, "sqlite_errorcode", None)
    if isinstance(code, int):
        return code & 0xFF in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
    return str(exc) in {"database is locked", "database table is locked"}


def _write_failure_diagnostic(
    path: Path,
    module: str,
    error_class: str,
    reason: str,
    exit_code: int | None,
    job_id: str | None = None,
) -> None:
    stage = module.rsplit(".", 1)[-1]
    safe_job_id = (
        job_id
        if type(job_id) is str
        and len(job_id) == 32
        and all(character in "0123456789abcdef" for character in job_id)
        else None
    )
    try:
        atomic_write(
            path,
            dumps(
                {
                    "outcome": "extraction_error",
                    "failed_stage": stage,
                    "error_class": error_class,
                    "child_exit_code": exit_code,
                    "reason": reason,
                }
            ),
        )
    except OSError:
        # Failure reporting must not replace the subprocess result or exception.
        pass
    logger.warning(
        "catalog subprocess failed stage=%s error_class=%s reason=%s "
        "exit_code=%s job_id=%s",
        stage,
        error_class,
        reason,
        exit_code,
        safe_job_id,
    )


def _filmo_output_tracks_present(
    payload: dict, records: tuple[dict, ...], probe: dict
) -> bool:
    streams = probe.get("streams")
    if type(streams) is not list:
        return False
    by_kind = {
        "audio": Counter(),
        "subtitle": Counter(),
    }
    counts = Counter()
    for stream in streams:
        if type(stream) is not dict:
            return False
        kind = stream.get("codec_type")
        if kind in by_kind:
            counts[kind] += 1
            tags = stream.get("tags")
            language = tags.get("language") if type(tags) is dict else None
            if type(language) is str:
                by_kind[kind][language] += 1

    metadata = payload.get("release_metadata")
    audio_languages = (
        metadata.get("audio_languages") if type(metadata) is dict else None
    )
    if type(audio_languages) is not list or counts["audio"] < len(audio_languages):
        return False
    for kind in ("audio", "subtitle"):
        expected = Counter(
            record["language"] for record in records if record["kind"] == kind
        )
        if any(by_kind[kind][language] < count for language, count in expected.items()):
            return False
    if metadata.get("subtitle_mode") == "soft":
        subtitle_languages = metadata.get("subtitle_languages")
        if type(subtitle_languages) is not list or any(
            by_kind["subtitle"][language] < 1 for language in subtitle_languages
        ):
            return False
    return True
