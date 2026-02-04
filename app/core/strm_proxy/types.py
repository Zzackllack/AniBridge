from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrmIdentity:
    """
    Identifies a specific episode stream for STRM proxying.
    """

    site: str
    slug: str
    season: int
    episode: int
    language: str
    provider: str | None = None

    def cache_key(self) -> tuple[str, str, int, int, str, str]:
        return (
            self.site,
            self.slug,
            self.season,
            self.episode,
            self.language,
            self.provider or "",
        )
