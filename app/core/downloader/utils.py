import re

from loguru import logger


def sanitize_filename(name: str) -> str:
    """
    Sanitize a filename by replacing filesystem-reserved characters with underscores and trimming whitespace.
    
    Replaces any occurrence of the characters \ / : * ? " < > | with an underscore, then strips leading and trailing whitespace.
    
    Parameters:
        name (str): Original filename to sanitize.
    
    Returns:
        str: The sanitized filename with reserved characters replaced by underscores and surrounding whitespace removed.
    """
    logger.debug("Sanitizing filename: %s", name)
    sanitized = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    logger.debug("Sanitized filename: %s", sanitized)
    return sanitized