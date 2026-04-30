import sys
from dataclasses import dataclass
from typing import Optional
from loguru import logger

from app.config import PROGRESS_FORCE_BAR, PROGRESS_STEP_PERCENT


def is_interactive_terminal() -> bool:
    """Detect if running in an interactive terminal.

    Honors PROGRESS_FORCE_BAR to override detection (useful under reloaders or
    when stdout is piped). Docker detection is informational; Docker can still
    be interactive if attached to a TTY.
    """
    try:
        # TerminalLogger preserves the real stdout.isatty()
        tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    except Exception:
        tty = False

    if PROGRESS_FORCE_BAR:
        logger.debug("Progress bar forced via PROGRESS_FORCE_BAR.")
        return True
    return tty


@dataclass
class ProgressSnapshot:
    downloaded: int = 0
    total: Optional[int] = None
    speed: Optional[float] = None
    eta: Optional[int] = None
    status: Optional[str] = None


class ProgressReporter:
    """Render download progress to terminal with minimal noise.

    - Interactive TTY: show a tqdm progress bar.
    - Non-interactive: print an info line every PROGRESS_STEP_PERCENT.
    """

    def __init__(
        self,
        label: str,
        *,
        unit: str = "B",
        unit_scale: bool = True,
    ) -> None:
        self.label = label
        self.unit = unit
        self.unit_scale = unit_scale
        self._bar = None
        self._last_step_pct = -1  # last printed step percentage (integer)
        self._interactive = is_interactive_terminal()

    def update(self, snap: ProgressSnapshot) -> None:
        total = snap.total
        downloaded = int(snap.downloaded or 0)

        # Initialize tqdm lazily when total is known (interactive only)
        if self._interactive and self._bar is None and total:
            try:
                from tqdm import tqdm  # local import to avoid dependency at import time

                # Send tqdm output directly to the underlying real stdout so it is NOT
                # duplicated into the terminal log file by TerminalLogger.
                bar_file = getattr(sys.stdout, "_stdout", None) or getattr(
                    sys, "__stdout__", sys.stdout
                )
                self._bar = tqdm(
                    total=int(total),
                    desc=self.label,
                    unit=self.unit,
                    unit_scale=self.unit_scale,
                    leave=True,
                    file=bar_file,
                    ascii=False,  # force unicode blocks (█▉▊▌ etc.)
                    dynamic_ncols=True,  # adapt to terminal width
                    mininterval=0.2,  # avoid excessive redraws
                )
            except Exception as e:
                logger.debug(
                    f"tqdm init failed, fallback to non-interactive style: {e}"
                )
                self._interactive = False

        # Render
        if self._bar is not None:
            # TTY progress bar
            self._bar.n = downloaded
            postfix = {}
            if snap.speed is not None:
                unit = self.unit
                unit_power = {
                    "B": 0,
                    "KB": 1,
                    "KiB": 1,
                    "MB": 2,
                    "MiB": 2,
                    "GB": 3,
                    "GiB": 3,
                    "TB": 4,
                    "TiB": 4,
                }.get(unit, 0)
                scaled_speed = float(snap.speed) / (1024**unit_power)
                postfix["Speed"] = f"{scaled_speed:.2f} {unit}/s"
            if snap.eta is not None:
                postfix["ETA"] = f"{int(snap.eta)}s"
            if postfix:
                self._bar.set_postfix(postfix)
            self._bar.refresh()
        else:
            # Non-interactive: print every N percent
            if total:
                try:
                    pct = int(max(0.0, min(100.0, downloaded / float(total) * 100.0)))
                except Exception:
                    pct = 0
                step = max(1, int(PROGRESS_STEP_PERCENT))
                if pct == 100 or pct // step > self._last_step_pct // step:
                    self._last_step_pct = pct
                    speed_unit = "MB/s" if self.unit == "B" else f"{self.unit}/s"
                    speed = (
                        f"{float(snap.speed) / (1024 * 1024):.2f} {speed_unit}"
                        if self.unit == "B" and snap.speed is not None
                        else f"{float(snap.speed):.2f} {speed_unit}"
                        if snap.speed is not None
                        else "-"
                    )
                    eta = f"{int(snap.eta)}s" if snap.eta is not None else "-"
                    progress_text = (
                        f"{downloaded}/{total} bytes"
                        if self.unit == "B"
                        else f"{downloaded}/{total} {self.unit}"
                    )
                    logger.info(
                        f"{self.label}: {pct}% ({progress_text}) speed={speed} eta={eta}"
                    )
            else:
                # Total unknown: avoid spamming; print on large increments
                threshold = 8 * 1024 * 1024  # 8 MiB
                if downloaded // threshold > self._last_step_pct:
                    self._last_step_pct = downloaded // threshold
                    suffix = "bytes" if self.unit == "B" else self.unit
                    logger.info(f"{self.label}: downloaded {downloaded} {suffix}...")

    def close(self) -> None:
        if self._bar is not None:
            try:
                self._bar.n = self._bar.total or self._bar.n
                self._bar.refresh()
                self._bar.close()
            except Exception:
                pass
            finally:
                self._bar = None
