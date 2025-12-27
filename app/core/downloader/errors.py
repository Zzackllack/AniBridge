from typing import List


class DownloadError(Exception):
    pass


class LanguageUnavailableError(DownloadError):
    """Requested language not offered by episode/site."""

    def __init__(self, requested: str, available: List[str]) -> None:
        self.requested = requested
        self.available = available
        super().__init__(
            f"Language '{requested}' not available. Available: {', '.join(available) or 'none'}"
        )
