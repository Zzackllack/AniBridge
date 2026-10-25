"""Supervise sequential transfer, remux and verification phases for a grab."""

import asyncio
import os
import signal
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
                    raise TimeoutError("local media phase deadline")
                if status and status.exists():
                    if status.stat().st_size > 65536:
                        raise ValueError("invalid child status")
                    record = loads(status.read_bytes(), 65536)
                    if record.get("phase") == "resolving" and now - started > 60:
                        raise TimeoutError("resolution deadline")
                    if record.get("phase") != previous_phase:
                        previous_phase, changed_at = record.get("phase"), now
                    update = record.get("progress")
                    if progress and update and update != previous_progress:
                        await database_call(progress, update)
                        if previous_progress is None or update.get(
                            "downloaded_bytes"
                        ) != previous_progress.get("downloaded_bytes"):
                            changed_at = now
                        previous_progress = update
                    if previous_phase == "downloading" and now - changed_at > 120:
                        raise TimeoutError("download inactivity")
                elif status and now - started > 60:
                    raise TimeoutError("resolution startup deadline")
                if activity:
                    size = activity.stat().st_size if activity.exists() else 0
                    if size != previous:
                        previous, changed_at = size, now
                    if now - changed_at > 120:
                        raise TimeoutError("local media phase stalled")
                try:
                    await asyncio.wait_for(process.wait(), 0.2)
                except TimeoutError:
                    pass
            detail, stdout = await asyncio.gather(errors, output)
            code = process.returncode
            if detail == b"diagnostic_limit" or stdout == b"diagnostic_limit":
                code, detail = -1, b"diagnostic_limit"
            if code and diagnostic:
                # FFmpeg/extractor messages can contain file metadata or URLs.
                # Retain only a closed classification, never the raw stderr.
                classes = {
                    b"Cannot allocate memory": "memory_limit",
                    b"not on whitelist": "unsupported_container",
                    b"Invalid data found": "invalid_media",
                    b"matches no streams": "missing_stream",
                    b"Timestamps are unset": "missing_timestamps",
                    b"diagnostic_limit": "diagnostic_limit",
                }
                reason = next(
                    (value for key, value in classes.items() if key in detail),
                    "media_process_failed",
                )
                atomic_write(
                    diagnostic,
                    dumps(
                        {
                            "outcome": "extraction_error",
                            "failed_stage": module.rsplit(".", 1)[-1],
                            "child_exit_code": process.returncode,
                            "reason": reason,
                        }
                    ),
                )
            return code
        finally:
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await asyncio.wait_for(asyncio.shield(process.wait()), 2)
            await asyncio.gather(errors, output)

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
                await database_call(
                    progress,
                    {
                        "downloaded_bytes": target.stat().st_size,
                        "total_bytes": target.stat().st_size,
                    },
                )
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
            tracks = [Path(path) for path in result.get("tracks", [])]
            if not 1 <= len(tracks) <= 2 or not all(
                path.is_file() and path.resolve().is_relative_to(attempt)
                for path in tracks
            ):
                return Outcome("extraction_error")
            remux = attempt / "verified.mkv"
            code = await self._run(
                "app.catalog.local_media_child",
                ["remux", str(attempt), str(remux), *map(str, tracks)],
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
            await database_call(
                progress,
                {
                    "downloaded_bytes": target.stat().st_size,
                    "total_bytes": target.stat().st_size,
                },
            )
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
