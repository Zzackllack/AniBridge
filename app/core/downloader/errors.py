from typing import List


class DownloadError(Exception):
    pass


class LanguageUnavailableError(DownloadError):
    """Requested language not offered by episode/site."""

    def __init__(self, requested: str, available: List[str]) -> None:
        """
        Initialize the exception with the requested language and available options.

        Parameters:
            requested (str): Language that was requested but is not offered.
            available (List[str]): Languages that are available for the resource; may be empty.

        Description:
            Stores `requested` and `available` on the instance and sets the exception message to
            "Language '<requested>' not available. Available: <comma-separated available list or 'none'>".
        """
        self.requested = requested
        self.available = available
        super().__init__(
            f"Language '{requested}' not available. Available: {', '.join(available) or 'none'}"
        )
