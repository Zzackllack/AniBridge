from __future__ import annotations

from dotenv import load_dotenv
from pathlib import Path
from app.utils.logger import config as configure_logger, ensure_log_path
from app.infrastructure.terminal_logger import TerminalLogger
from loguru import logger
from app.config import DATA_DIR, CATALOG_CONFIG


def init() -> None:
    """Initialize environment and logging early.

    - Loads .env
    - Configures loguru
    - Ensures log path exists under DATA_DIR
    - Installs TerminalLogger to mirror stdout/stderr to file
    """
    load_dotenv()
    configure_logger()
    ensure_log_path(DATA_DIR)
    TerminalLogger(DATA_DIR)
    enabled = ", ".join(
        f"{entry['site_id']}@{entry['base_url']}"
        for entry in CATALOG_CONFIG
    )
    logger.info(f"Enabled catalogues: {enabled}")
