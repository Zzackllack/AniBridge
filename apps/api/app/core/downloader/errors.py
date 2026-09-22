from typing import List


class DownloadError(Exception):
    """Base exception for downloader failures and retry exhaustion."""


class ProviderResolutionError(DownloadError):
    """Base exception for a classified catalogue or video-host failure."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        status_code: int | None = None,
        host: str | None = None,
    ) -> None:
        self.stage = stage
        self.status_code = status_code
        self.host = host
        super().__init__(message)


class ProviderUnavailableError(ProviderResolutionError):
    """Requested video host is not offered for the selected language."""


class ProviderVerificationRequiredError(ProviderResolutionError):
    """Provider access is blocked by a challenge requiring user verification."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        status_code: int | None = None,
        host: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            message,
            stage=stage,
            status_code=status_code,
            host=host,
        )


class ProviderTransportError(ProviderResolutionError):
    """Provider request failed temporarily or returned a retryable status."""


class SourceUnavailableError(ProviderResolutionError):
    """Provider confirmed that the requested source no longer exists."""


class UnsupportedProviderResponseError(ProviderResolutionError):
    """Provider returned a successful but unrecognized response shape."""


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
