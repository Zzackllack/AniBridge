from __future__ import annotations

from dotenv import load_dotenv
from app.utils.logger import config as configure_logger, ensure_log_path
from app.infrastructure.terminal_logger import TerminalLogger
from app.config import DATA_DIR


def init() -> None:
    """Initialize environment and logging early.

    - Loads .env
    - Configures loguru
    - Ensures log path exists under DATA_DIR
    - Installs TerminalLogger to mirror stdout/stderr to file
    - Configures loguru after the terminal tee is installed
    """
    load_dotenv()
    ensure_log_path(DATA_DIR)
    TerminalLogger(DATA_DIR)
    # Loguru retains the stream object passed to logger.add(). Configure it
    # after installing the tee so structured application logs reach the file.
    configure_logger()
