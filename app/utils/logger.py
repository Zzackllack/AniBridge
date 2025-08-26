import os
import sys
from loguru import logger
from pathlib import Path
from datetime import datetime
import uuid
from typing import Optional


def config():
    """
    Configure the global Loguru logger. Keeps this function lightweight so it
    can be imported across the codebase without side-effects.
    """
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.remove()
    logger.add(
        sys.stdout,
        level=LOG_LEVEL,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )


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
