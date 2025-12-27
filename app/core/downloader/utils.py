import re

from loguru import logger


def sanitize_filename(name: str) -> str:
    """Sanitize a filename (name: str) and return the safe filesystem name."""
    logger.debug("Sanitizing filename: {}", name)
    sanitized = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    logger.debug("Sanitized filename: {}", sanitized)
    return sanitized
