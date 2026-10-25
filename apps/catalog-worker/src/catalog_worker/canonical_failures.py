"""Safe canonical failure codes; exception messages and payloads stay private."""

from dataclasses import dataclass
from typing import Self

from catalog_core.json_codec import ContractError

PHASES = frozenset(
    {"search", "descriptor", "translation", "parent", "identifiers", "cache"}
)
REASONS = frozenset(
    {
        "http_error",
        "rate_limited",
        "not_found",
        "challenge_or_block",
        "transport_failure",
        "local_resource",
        "invalid_json",
        "invalid_payload",
        "timeout",
        "local_io",
        "descriptor_identity_conflict",
        "translation_identity_conflict",
        "episode_parent_conflict",
        "episode_coordinate_conflict",
        "episode_identity_conflict",
        "episode_identity_missing",
        "parent_id_mismatch",
        "parent_imdb_mismatch",
        "metadata_namespace_mismatch",
    }
)


class EvidenceError(ContractError):
    """Attach a fixed code where the evidence check knows the actual failure."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason if reason in REASONS else "invalid_payload"


def verify(condition: bool, reason: str, message: str) -> None:
    """Reject invalid evidence without parsing exception text for diagnostics."""
    if not condition:
        raise EvidenceError(reason, message)


class CanonicalUnavailable(ValueError):
    """Transport failure without response text, endpoints or search terms."""

    def __init__(
        self,
        retry_after: int | None,
        *,
        reason: str = "transport_failure",
        status: int | None = None,
    ) -> None:
        super().__init__("canonical unavailable")
        self.retry_after = retry_after
        self.reason = reason if reason in REASONS else "transport_failure"
        self.status = status


@dataclass(frozen=True)
class Failure:
    phase: str
    reason: str
    http_status: int | None = None

    @classmethod
    def from_error(cls, phase: str, error: Exception) -> Self:
        """Classify typed errors only; never inspect their messages or repr."""
        if isinstance(error, CanonicalUnavailable):
            return cls(phase, error.reason, error.status)
        if isinstance(error, EvidenceError):
            return cls(phase, error.reason)
        if isinstance(error, TimeoutError):
            return cls(phase, "timeout")
        if isinstance(error, OSError):
            return cls(phase, "local_io")
        return cls(phase, "invalid_payload")


def request_phase(path: str) -> str:
    """Classify known request routes; the path itself never enters a report."""
    if path.startswith("/v2/tvdb/shows/"):
        return "descriptor" if path.startswith("/v2/tvdb/shows/eng/") else "translation"
    if path.startswith(("/v1/tvdb/shows/", "/3/movie/")):
        return "descriptor"
    return "search"
