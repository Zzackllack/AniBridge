import os
import sys
from loguru import logger
from pathlib import Path
from datetime import datetime
import uuid
from typing import Optional
import logging

_STDLIB_LOGGING_CONFIGURED = False

# Ensure terminal duplication is active before any logger sinks attach.
# This guarantees Loguru sinks bound to sys.stdout are teed into the file.
try:
    # Avoid circular imports: terminal_logger has no dependency on this module.
    from app.infrastructure.terminal_logger import TerminalLogger  # type: ignore
except Exception:
    TerminalLogger = None  # type: ignore


def config():
    """
    Configure the global Loguru logger. Keeps this function lightweight so it
    can be imported across the codebase without side-effects.
    """
    global _STDLIB_LOGGING_CONFIGURED
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.remove()
    logger.add(
        sys.stdout,
        level=LOG_LEVEL,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    if not _STDLIB_LOGGING_CONFIGURED:

        class _InterceptHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                try:
                    level = logger.level(record.levelname).name
                except ValueError:
                    level = record.levelno
                frame, depth = logging.currentframe(), 2
                while frame and frame.f_code.co_filename == logging.__file__:
                    frame = frame.f_back
                    depth += 1
                logger.opt(depth=depth, exception=record.exc_info).log(
                    level, record.getMessage()
                )

        intercept_handler = _InterceptHandler()
        logging.basicConfig(handlers=[intercept_handler], level=LOG_LEVEL, force=True)
        logging.captureWarnings(True)
        logging.lastResort = None
        for name in (
            "uvicorn",
            "uvicorn.error",
            "uvicorn.access",
            "urllib3",
            "urllib3.connectionpool",
            "watchfiles",
            "watchfiles.main",
        ):
            log = logging.getLogger(name)
            log.handlers = [intercept_handler]
            log.propagate = False
            if name.startswith("watchfiles"):
                log.setLevel(logging.WARNING)
        _STDLIB_LOGGING_CONFIGURED = True


def ensure_log_path(base_dir: Optional[Path] = None) -> Path:
    """
    Ensure ANIBRIDGE_LOG_PATH is set. If the environment variable is not set,
    create a timestamped unique log file path under `base_dir` (defaults to
    CWD / data) and set ANIBRIDGE_LOG_PATH to that path. The containing
    directory will be created if necessary.

    Returns the Path to the log file.
    """
    env = os.environ.get("ANIBRIDGE_LOG_PATH")
    if env:
        return Path(env)

    base = Path.cwd() / "data" if base_dir is None else base_dir
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_id = uuid.uuid4().hex[:8]
    log_path = base / f"terminal-{ts}-{run_id}.log"
    # Ensure directory exists
    log_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["ANIBRIDGE_LOG_PATH"] = str(log_path)
    return log_path


# Initialize TerminalLogger early so that any subsequent logger.add(sys.stdout)
# writes are captured by the tee and end up in the file as well. This preserves
# historical behavior where the terminal log contains full Loguru output.
def _init_terminal_tee_early() -> None:
    try:
        # Ensure env path exists so TerminalLogger picks it up
        log_path = ensure_log_path()
        if TerminalLogger is not None:
            # Instantiate singleton; safe to call multiple times
            TerminalLogger(log_path.parent)
    except Exception:
        # Never fail app startup because of logging setup
        pass


# Run early initialization at import time
_init_terminal_tee_early()
