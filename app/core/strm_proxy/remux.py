from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import anyio
from loguru import logger

from app.config import (
    STRM_PROXY_HLS_HINT_BANDWIDTH,
    STRM_PROXY_HLS_REMUX_BUILD_TIMEOUT_SECONDS,
    STRM_PROXY_HLS_REMUX_CACHE_DIR,
    STRM_PROXY_HLS_REMUX_CACHE_TTL_SECONDS,
    STRM_PROXY_HLS_REMUX_CACHED_ENABLED,
    STRM_PROXY_HLS_REMUX_FAIL_COOLDOWN_SECONDS,
    STRM_PROXY_HLS_REMUX_MAX_CONCURRENT_BUILDS,
)

from .types import StrmIdentity

_REMUX_CONFIG_VERSION = "v1-file-mp4-copy-faststart"
_MIN_VALID_DURATION_SECONDS = 30.0
_POLL_INTERVAL_SECONDS = 0.25
_STALE_LOCK_GRACE_SECONDS = 30
_CLEANUP_INTERVAL_SECONDS = 300
_FFMPEG_BIN = "ffmpeg"
_FFPROBE_BIN = "ffprobe"

_VOLATILE_QUERY_KEYS = {
    "exp",
    "expires",
    "sig",
    "signature",
    "token",
    "auth",
    "hmac",
    "x-amz-signature",
    "x-amz-date",
    "x-amz-expires",
    "x-amz-security-token",
    "x-amz-credential",
    "policy",
    "key-pair-id",
}


@dataclass(frozen=True)
class RemuxPaths:
    key: str
    artifact_path: Path
    meta_path: Path
    lock_path: Path
    temp_path: Path


@dataclass(frozen=True)
class RemuxDecision:
    artifact_path: Path | None
    cache_key: str
    source_fingerprint: str
    state: str
    fallback_reason: str | None = None


class RemuxCacheManager:
    """
    Manage file-backed HLS remux artifacts used by /strm/stream.
    """

    def __init__(
        self,
        *,
        enabled: bool,
        cache_dir: Path,
        cache_ttl_seconds: int,
        build_timeout_seconds: int,
        max_concurrent_builds: int,
        fail_cooldown_seconds: int,
    ) -> None:
        self._enabled = enabled
        self._cache_dir = cache_dir
        self._cache_ttl_seconds = max(0, cache_ttl_seconds)
        self._build_timeout_seconds = max(1, build_timeout_seconds)
        self._max_concurrent_builds = max(1, max_concurrent_builds)
        self._fail_cooldown_seconds = max(0, fail_cooldown_seconds)
        self._build_wait_seconds = max(1.0, min(5.0, self._build_timeout_seconds / 40))
        self._default_video_bitrate = max(STRM_PROXY_HLS_HINT_BANDWIDTH, 192_000)

        self._build_slots = asyncio.Semaphore(self._max_concurrent_builds)
        self._task_lock = asyncio.Lock()
        self._build_tasks: dict[str, asyncio.Task[None]] = {}
        self._metrics_lock = threading.Lock()
        self._metrics: Counter[str] = Counter()
        self._last_cleanup_monotonic = 0.0

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def maybe_cleanup(self, *, force: bool = False) -> None:
        """
        Periodically remove stale temp/lock/meta/artifact files.
        """
        if not self._enabled:
            return
        now_mono = time.monotonic()
        if (
            not force
            and (now_mono - self._last_cleanup_monotonic) < _CLEANUP_INTERVAL_SECONDS
        ):
            return
        self._last_cleanup_monotonic = now_mono
        await anyio.to_thread.run_sync(self._cleanup_sync)

    def metrics_snapshot(self) -> dict[str, int]:
        """
        Return a copy of in-memory remux counters.
        """
        with self._metrics_lock:
            return dict(self._metrics)

    async def ensure_artifact(
        self,
        *,
        identity: StrmIdentity,
        upstream_url: str,
        request_id: str,
    ) -> RemuxDecision:
        """
        Return a ready remux artifact or a fallback decision.
        """
        if not self._enabled:
            return RemuxDecision(
                artifact_path=None,
                cache_key="",
                source_fingerprint="",
                state="disabled",
                fallback_reason="disabled",
            )

        await self.maybe_cleanup(force=False)

        source_fingerprint = self._source_fingerprint(upstream_url)
        cache_key = self._cache_key(identity, source_fingerprint)
        paths = self._paths(cache_key)
        state, meta = self._state(paths, source_fingerprint)

        logger.debug(
            "STRM remux state request_id={} key={} state={} source={}",
            request_id,
            cache_key,
            state,
            source_fingerprint,
        )

        if state == "ready":
            self._metric_inc("cache_hit")
            return RemuxDecision(
                artifact_path=paths.artifact_path,
                cache_key=cache_key,
                source_fingerprint=source_fingerprint,
                state=state,
            )

        if state == "failed":
            reason = str((meta or {}).get("failure_reason") or "failed_cooldown")
            self._metric_inc(f"fallback:{reason}")
            return RemuxDecision(
                artifact_path=None,
                cache_key=cache_key,
                source_fingerprint=source_fingerprint,
                state=state,
                fallback_reason=reason,
            )

        if state == "building":
            waited = await self._wait_for_ready(paths, source_fingerprint)
            if waited.artifact_path is not None:
                self._metric_inc("cache_hit_after_wait")
                return waited
            self._metric_inc("fallback:lock_wait_exceeded")
            return RemuxDecision(
                artifact_path=None,
                cache_key=cache_key,
                source_fingerprint=source_fingerprint,
                state="building",
                fallback_reason=waited.fallback_reason or "lock_wait_exceeded",
            )

        started = await self._start_build(
            paths=paths,
            source_url=upstream_url,
            source_fingerprint=source_fingerprint,
            request_id=request_id,
        )
        if not started:
            waited = await self._wait_for_ready(paths, source_fingerprint)
            if waited.artifact_path is not None:
                self._metric_inc("cache_hit_after_wait")
                return waited
            self._metric_inc("fallback:lock_wait_exceeded")
            return RemuxDecision(
                artifact_path=None,
                cache_key=cache_key,
                source_fingerprint=source_fingerprint,
                state="building",
                fallback_reason=waited.fallback_reason or "lock_wait_exceeded",
            )

        waited = await self._wait_for_ready(paths, source_fingerprint)
        if waited.artifact_path is not None:
            self._metric_inc("build_sync_success")
            return waited
        self._metric_inc("fallback:build_in_progress")
        return RemuxDecision(
            artifact_path=None,
            cache_key=cache_key,
            source_fingerprint=source_fingerprint,
            state="building",
            fallback_reason=waited.fallback_reason or "build_in_progress",
        )

    async def _start_build(
        self,
        *,
        paths: RemuxPaths,
        source_url: str,
        source_fingerprint: str,
        request_id: str,
    ) -> bool:
        async with self._task_lock:
            existing = self._build_tasks.get(paths.key)
            if existing and not existing.done():
                return True
            if existing and existing.done():
                self._build_tasks.pop(paths.key, None)

            if not self._acquire_lock(paths.lock_path):
                return False

            task = asyncio.create_task(
                self._run_build(
                    paths=paths,
                    source_url=source_url,
                    source_fingerprint=source_fingerprint,
                    request_id=request_id,
                ),
                name=f"strm-remux-{paths.key[:12]}",
            )
            self._build_tasks[paths.key] = task
            return True

    async def _run_build(
        self,
        *,
        paths: RemuxPaths,
        source_url: str,
        source_fingerprint: str,
        request_id: str,
    ) -> None:
        started = time.monotonic()
        failure_reason: str | None = None
        failure_error: str | None = None
        try:
            async with self._build_slots:
                await anyio.to_thread.run_sync(
                    lambda: paths.artifact_path.parent.mkdir(
                        parents=True, exist_ok=True
                    )
                )
                self._safe_unlink(paths.temp_path)

                ffmpeg_cmd = self._ffmpeg_cmd(source_url, paths.temp_path)
                rc, _stdout, stderr, timed_out = await self._run_command(
                    ffmpeg_cmd, timeout_seconds=self._build_timeout_seconds
                )
                if timed_out:
                    failure_reason = "timeout"
                    failure_error = (
                        f"ffmpeg timed out after {self._build_timeout_seconds}s"
                    )
                    return
                if rc != 0:
                    failure_reason = "ffmpeg_error"
                    failure_error = (stderr or "").strip()[:1000]
                    return
                if not paths.temp_path.exists() or paths.temp_path.stat().st_size <= 0:
                    failure_reason = "ffmpeg_error"
                    failure_error = "ffmpeg produced an empty artifact"
                    return

                probe = await self._probe_artifact(paths.temp_path)
                if probe["valid"] is not True:
                    failure_reason = "probe_invalid"
                    failure_error = str(probe.get("error") or "probe validation failed")
                    return

                os.replace(paths.temp_path, paths.artifact_path)
                built_at = time.time()
                expires_at = (
                    built_at + self._cache_ttl_seconds
                    if self._cache_ttl_seconds > 0
                    else 0
                )
                meta_payload: dict[str, Any] = {
                    "status": "ready",
                    "cache_key": paths.key,
                    "source_fingerprint": source_fingerprint,
                    "remux_version": _REMUX_CONFIG_VERSION,
                    "built_at_ts": built_at,
                    "expires_at_ts": expires_at,
                    "artifact_size_bytes": int(paths.artifact_path.stat().st_size),
                    "duration_seconds": probe.get("duration_seconds"),
                    "video_bitrate": probe.get("video_bitrate"),
                    "container_bitrate": probe.get("container_bitrate"),
                    "inferred_video_bitrate": probe.get("inferred_video_bitrate"),
                    "build_duration_ms": int((time.monotonic() - started) * 1000),
                }
                self._write_meta(paths.meta_path, meta_payload)
                self._metric_inc("build_success")
                logger.success(
                    "STRM remux build success request_id={} key={} size={} duration={} bitrate={}",
                    request_id,
                    paths.key,
                    meta_payload["artifact_size_bytes"],
                    meta_payload["duration_seconds"],
                    meta_payload["video_bitrate"]
                    or meta_payload["inferred_video_bitrate"],
                )
        except Exception as exc:
            failure_reason = "ffmpeg_error"
            failure_error = str(exc)
            logger.exception(
                "STRM remux build failed with exception request_id={} key={}",
                request_id,
                paths.key,
            )
        finally:
            if failure_reason is not None:
                failed_payload = {
                    "status": "failed",
                    "cache_key": paths.key,
                    "source_fingerprint": source_fingerprint,
                    "remux_version": _REMUX_CONFIG_VERSION,
                    "failure_reason": failure_reason,
                    "failure_error": failure_error or "",
                    "failed_at_ts": time.time(),
                    "build_duration_ms": int((time.monotonic() - started) * 1000),
                }
                self._write_meta(paths.meta_path, failed_payload)
                self._metric_inc(f"build_failure:{failure_reason}")
                logger.warning(
                    "STRM remux build failed request_id={} key={} reason={} error={}",
                    request_id,
                    paths.key,
                    failure_reason,
                    failure_error or "",
                )
            self._safe_unlink(paths.temp_path)
            self._safe_unlink(paths.lock_path)
            async with self._task_lock:
                self._build_tasks.pop(paths.key, None)

    async def _wait_for_ready(
        self, paths: RemuxPaths, source_fingerprint: str
    ) -> RemuxDecision:
        deadline = time.monotonic() + self._build_wait_seconds
        while time.monotonic() < deadline:
            state, meta = self._state(paths, source_fingerprint)
            if state == "ready":
                return RemuxDecision(
                    artifact_path=paths.artifact_path,
                    cache_key=paths.key,
                    source_fingerprint=source_fingerprint,
                    state=state,
                )
            if state == "failed":
                return RemuxDecision(
                    artifact_path=None,
                    cache_key=paths.key,
                    source_fingerprint=source_fingerprint,
                    state=state,
                    fallback_reason=str(
                        (meta or {}).get("failure_reason") or "failed_cooldown"
                    ),
                )
            await anyio.sleep(_POLL_INTERVAL_SECONDS)
        return RemuxDecision(
            artifact_path=None,
            cache_key=paths.key,
            source_fingerprint=source_fingerprint,
            state="building",
            fallback_reason="lock_wait_exceeded",
        )

    def _state(
        self, paths: RemuxPaths, source_fingerprint: str
    ) -> tuple[str, dict[str, Any] | None]:
        self._cleanup_stale_lock(paths.lock_path)
        meta = self._read_meta(paths.meta_path)
        now = time.time()

        if self._is_ready(paths, meta, source_fingerprint, now):
            return "ready", meta

        if paths.lock_path.exists():
            return "building", meta

        if self._is_failed_and_cooling_down(meta, source_fingerprint, now):
            return "failed", meta

        if paths.artifact_path.exists() and not self._is_ready(
            paths, meta, source_fingerprint, now
        ):
            self._safe_unlink(paths.artifact_path)
        return "missing", meta

    def _is_ready(
        self,
        paths: RemuxPaths,
        meta: dict[str, Any] | None,
        source_fingerprint: str,
        now: float,
    ) -> bool:
        if not paths.artifact_path.exists():
            return False
        if not meta or meta.get("status") != "ready":
            return False
        if meta.get("source_fingerprint") != source_fingerprint:
            return False
        if meta.get("remux_version") != _REMUX_CONFIG_VERSION:
            return False
        expires_at = self._parse_float(meta.get("expires_at_ts")) or 0.0
        if expires_at > 0 and expires_at <= now:
            self._safe_unlink(paths.artifact_path)
            self._safe_unlink(paths.meta_path)
            return False
        return True

    def _is_failed_and_cooling_down(
        self,
        meta: dict[str, Any] | None,
        source_fingerprint: str,
        now: float,
    ) -> bool:
        if not meta or meta.get("status") != "failed":
            return False
        if meta.get("source_fingerprint") != source_fingerprint:
            return False
        if meta.get("remux_version") != _REMUX_CONFIG_VERSION:
            return False
        if self._fail_cooldown_seconds <= 0:
            return False
        failed_at = self._parse_float(meta.get("failed_at_ts")) or 0.0
        return (now - failed_at) < self._fail_cooldown_seconds

    def _acquire_lock(self, lock_path: Path) -> bool:
        self._cleanup_stale_lock(lock_path)
        try:
            fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            return False
        try:
            lock_payload = {
                "pid": os.getpid(),
                "created_at_ts": time.time(),
            }
            os.write(fd, json.dumps(lock_payload).encode("utf-8"))
        finally:
            os.close(fd)
        return True

    def _cleanup_stale_lock(self, lock_path: Path) -> None:
        if not lock_path.exists():
            return
        try:
            age = time.time() - lock_path.stat().st_mtime
        except OSError:
            return
        if age <= (self._build_timeout_seconds + _STALE_LOCK_GRACE_SECONDS):
            return
        logger.warning(
            "Removing stale STRM remux lock {} age={:.1f}s", lock_path.name, age
        )
        self._safe_unlink(lock_path)

    async def _probe_artifact(self, artifact_path: Path) -> dict[str, Any]:
        cmd = [
            _FFPROBE_BIN,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-print_format",
            "json",
            str(artifact_path),
        ]
        timeout = min(30, self._build_timeout_seconds)
        rc, stdout, stderr, timed_out = await self._run_command(
            cmd, timeout_seconds=timeout
        )
        if timed_out:
            return {"valid": False, "error": "ffprobe timed out"}
        if rc != 0:
            return {"valid": False, "error": (stderr or "").strip() or "ffprobe failed"}
        try:
            data = json.loads(stdout or "{}")
        except json.JSONDecodeError:
            return {"valid": False, "error": "ffprobe produced invalid json"}

        streams = data.get("streams") or []
        video_stream = next(
            (stream for stream in streams if stream.get("codec_type") == "video"), None
        )
        if not isinstance(video_stream, dict):
            return {"valid": False, "error": "missing video stream"}

        fmt = data.get("format") or {}
        if not isinstance(fmt, dict):
            fmt = {}

        duration = self._parse_float(video_stream.get("duration")) or self._parse_float(
            fmt.get("duration")
        )
        if not duration or duration < _MIN_VALID_DURATION_SECONDS:
            return {"valid": False, "error": "duration below threshold"}

        container_bitrate = self._parse_int(fmt.get("bit_rate"))
        video_bitrate = self._parse_int(video_stream.get("bit_rate"))
        if video_bitrate is None:
            tags = video_stream.get("tags")
            if isinstance(tags, dict):
                video_bitrate = self._parse_int(tags.get("BPS")) or self._parse_int(
                    tags.get("BPS-eng")
                )
        size_bytes = self._parse_int(fmt.get("size")) or int(
            artifact_path.stat().st_size
        )
        inferred_video_bitrate = (
            int((size_bytes * 8) / duration)
            if size_bytes > 0 and duration > 0
            else None
        )
        effective_video_bitrate = (
            video_bitrate or container_bitrate or inferred_video_bitrate
        )
        if effective_video_bitrate is None or effective_video_bitrate <= 0:
            return {"valid": False, "error": "missing usable bitrate"}

        return {
            "valid": True,
            "duration_seconds": round(duration, 3),
            "video_bitrate": video_bitrate,
            "container_bitrate": container_bitrate,
            "inferred_video_bitrate": inferred_video_bitrate,
        }

    def _ffmpeg_cmd(self, source_url: str, output_path: Path) -> list[str]:
        return [
            _FFMPEG_BIN,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            source_url,
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-map",
            "-0:s?",
            "-map",
            "-0:d?",
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-fflags",
            "+genpts",
            "-avoid_negative_ts",
            "make_zero",
            "-movflags",
            "+faststart",
            "-metadata:s:v:0",
            f"BPS={self._default_video_bitrate}",
            "-metadata:s:v:0",
            f"BPS-eng={self._default_video_bitrate}",
            "-f",
            "mp4",
            str(output_path),
        ]

    async def _run_command(
        self, cmd: list[str], *, timeout_seconds: int
    ) -> tuple[int, str, str, bool]:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        timed_out = False
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            timed_out = True
            process.kill()
            stdout_bytes, stderr_bytes = await process.communicate()
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        return process.returncode or 0, stdout, stderr, timed_out

    def _read_meta(self, meta_path: Path) -> dict[str, Any] | None:
        if not meta_path.exists():
            return None
        try:
            raw = meta_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            logger.warning("Failed reading STRM remux meta {}", meta_path.name)
        return None

    def _write_meta(self, meta_path: Path, payload: dict[str, Any]) -> None:
        tmp_path = Path(f"{meta_path}.tmp")
        try:
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(
                json.dumps(payload, sort_keys=True, ensure_ascii=True),
                encoding="utf-8",
            )
            os.replace(tmp_path, meta_path)
        finally:
            self._safe_unlink(tmp_path)

    def _cache_key(self, identity: StrmIdentity, source_fingerprint: str) -> str:
        key_payload = {
            "site": identity.site,
            "slug": identity.slug,
            "season": identity.season,
            "episode": identity.episode,
            "language": identity.language,
            "provider": identity.provider or "",
            "source_fingerprint": source_fingerprint,
            "remux_version": _REMUX_CONFIG_VERSION,
        }
        canonical = json.dumps(
            key_payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _source_fingerprint(self, upstream_url: str) -> str:
        parsed = urlsplit(upstream_url)
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        filtered = [
            (k, v) for k, v in pairs if k.strip().lower() not in _VOLATILE_QUERY_KEYS
        ]
        filtered.sort()
        query_canonical = "&".join(f"{k}={v}" for k, v in filtered)
        value = (
            f"{parsed.scheme.lower()}://{(parsed.netloc or '').lower()}{parsed.path}"
            f"?{query_canonical}"
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]

    def _paths(self, key: str) -> RemuxPaths:
        return RemuxPaths(
            key=key,
            artifact_path=self._cache_dir / f"{key}.mp4",
            meta_path=self._cache_dir / f"{key}.meta.json",
            lock_path=self._cache_dir / f"{key}.lock",
            temp_path=self._cache_dir / f"{key}.tmp.mp4",
        )

    def _cleanup_sync(self) -> None:
        if not self._cache_dir.exists():
            return
        try:
            entries = list(self._cache_dir.iterdir())
        except OSError:
            return
        now = time.time()

        for entry in entries:
            if not entry.is_file():
                continue
            name = entry.name
            if name.endswith(".lock"):
                self._cleanup_stale_lock(entry)
                continue
            if name.endswith(".tmp.mp4"):
                if self._age_seconds(entry, now) > self._build_timeout_seconds:
                    self._safe_unlink(entry)
                continue
            if not name.endswith(".meta.json"):
                continue

            meta = self._read_meta(entry)
            if not meta:
                continue
            key = name[: -len(".meta.json")]
            paths = self._paths(key)
            status = str(meta.get("status") or "")
            if status == "ready":
                expires_at = self._parse_float(meta.get("expires_at_ts")) or 0.0
                if expires_at > 0 and expires_at <= now:
                    self._safe_unlink(paths.artifact_path)
                    self._safe_unlink(paths.meta_path)
                continue
            if status == "failed":
                failed_at = self._parse_float(meta.get("failed_at_ts")) or 0.0
                keep_for = max(3600, self._fail_cooldown_seconds)
                if failed_at > 0 and (now - failed_at) > keep_for:
                    self._safe_unlink(paths.meta_path)

    def _metric_inc(self, key: str) -> None:
        with self._metrics_lock:
            self._metrics[key] += 1

    def _age_seconds(self, path: Path, now: float) -> float:
        try:
            return max(0.0, now - path.stat().st_mtime)
        except OSError:
            return 0.0

    def _safe_unlink(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def _parse_float(self, value: Any) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if parsed <= 0:
            return None
        return parsed

    def _parse_int(self, value: Any) -> int | None:
        try:
            parsed = int(str(value))
        except (TypeError, ValueError):
            return None
        if parsed <= 0:
            return None
        return parsed


REMUX_CACHE_MANAGER = RemuxCacheManager(
    enabled=STRM_PROXY_HLS_REMUX_CACHED_ENABLED,
    cache_dir=STRM_PROXY_HLS_REMUX_CACHE_DIR,
    cache_ttl_seconds=STRM_PROXY_HLS_REMUX_CACHE_TTL_SECONDS,
    build_timeout_seconds=STRM_PROXY_HLS_REMUX_BUILD_TIMEOUT_SECONDS,
    max_concurrent_builds=STRM_PROXY_HLS_REMUX_MAX_CONCURRENT_BUILDS,
    fail_cooldown_seconds=STRM_PROXY_HLS_REMUX_FAIL_COOLDOWN_SECONDS,
)
