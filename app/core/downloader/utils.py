import re

from loguru import logger


def sanitize_filename(name: str) -> str:
    logger.debug("Sanitizing filename: %s", name)
    sanitized = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    logger.debug("Sanitized filename: %s", sanitized)
    return sanitized
