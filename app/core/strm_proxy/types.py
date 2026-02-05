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
        """
        Create a stable tuple key that uniquely identifies this stream instance for caching or deduplication.
        
        Returns:
            tuple[str, str, int, int, str, str]: A 6-tuple containing (site, slug, season, episode, language, provider) where `provider` is the empty string if the instance's provider is `None`.
        """
        return (
            self.site,
            self.slug,
            self.season,
            self.episode,
            self.language,
            self.provider or "",
        )