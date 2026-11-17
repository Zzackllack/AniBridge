"""Terminal progress for durable catalog jobs, bounded to what is true.

The legacy scheduler renders through :mod:`app.utils.terminal`, which is where
``PROGRESS_FORCE_BAR`` and ``PROGRESS_STEP_PERCENT`` are honored. Durable catalog
jobs supervise children instead and never call that renderer. This adapter
reuses it without presenting a finished transfer as a finished publication.
"""

from collections.abc import Callable, Mapping
import math

from loguru import logger

from app.utils.terminal import ProgressReporter, ProgressSnapshot


class JobProgress(ProgressReporter):
    """Per-job reporter that only announces 100% after publication."""

    def __init__(self, label: str) -> None:
        super().__init__(label, log_steps=True)
        self._published = False

    def update(self, snap: ProgressSnapshot) -> None:
        """Ignore a full transfer until the publisher confirms the output."""
        if not self._published and snap.total and snap.downloaded >= snap.total:
            # The child reports transfer completion, but remux, probe and
            # publication still have to happen. Keep the last incomplete sample.
            return
        super().update(snap)

    def finish(self, *, published: bool, size: int | None = None) -> None:
        """Complete a published job or discard the display of a failed attempt."""
        if published and size:
            self._published = True
            super().update(ProgressSnapshot(downloaded=size, total=size))
            super().close()
            return
        # ProgressReporter.close() fills the bar; a failed attempt must not.
        if self._bar is not None:
            try:
                self._bar.close()
            finally:
                self._bar = None


class JobProgressLog:
    """One reporter per active job so concurrent downloads cannot share a bar."""

    def __init__(self, factory: Callable[[str], JobProgress] = JobProgress) -> None:
        self._factory = factory
        self._jobs: dict[str, JobProgress] = {}

    def start(self, job_id: str) -> None:
        """Create one display for an admitted attempt."""
        # A duplicate claim would otherwise leak the previous tqdm handle.
        self.finish(job_id)
        try:
            self._jobs[job_id] = self._factory(f"Job {job_id}")
        except Exception as exc:  # noqa: BLE001 -- display never fails admission
            logger.debug(
                "Catalog progress display unavailable: job_id={}, error_class={}",
                job_id,
                type(exc).__name__,
            )

    def update(self, job_id: str, update: Mapping[str, object]) -> None:
        """Render one snapshot; an unknown job is ignored, never an error."""
        reporter = self._jobs.get(job_id)
        if reporter is None:
            return
        try:
            reporter.update(_snapshot(update))
        except Exception as exc:  # noqa: BLE001 -- display never fails a transfer
            # Drop the reporter instead of repeating a broken render every byte.
            self.finish(job_id)
            logger.debug(
                "Catalog progress rendering disabled: job_id={}, error_class={}",
                job_id,
                type(exc).__name__,
            )

    def finish(
        self,
        job_id: str,
        *,
        published: bool = False,
        size: int | None = None,
    ) -> None:
        """Publish a completed bar or discard the display of an attempt."""
        reporter = self._jobs.pop(job_id, None)
        if reporter is None:
            return
        try:
            reporter.finish(published=published, size=size)
        except Exception as exc:  # noqa: BLE001 -- display never fails completion
            logger.debug(
                "Catalog progress close failed: job_id={}, error_class={}",
                job_id,
                type(exc).__name__,
            )

    def close(self) -> None:
        """Discard every remaining display during runner shutdown."""
        for job_id in list(self._jobs):
            self.finish(job_id)


def _snapshot(update: Mapping[str, object]) -> ProgressSnapshot:
    """Map one durable progress record to the legacy renderer's snapshot."""
    return ProgressSnapshot(
        downloaded=_integer(update.get("downloaded_bytes")) or 0,
        total=_integer(update.get("total_bytes")) or None,
        speed=_number(update.get("speed")),
        eta=_integer(update.get("eta")),
    )


def _integer(value: object) -> int | None:
    number = _number(value)
    return None if number is None else max(0, int(number))


def _number(value: object) -> float | None:
    # bool is an int subclass, but a JSON boolean is not a byte count.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None
