from __future__ import annotations

from dataclasses import dataclass, field

from app.core.downloader.errors import LanguageUnavailableError
from app.providers.sto.v2 import fetch_episode_provider_data


@dataclass(slots=True)
class SerienstreamSource:
    """Lazy Serienstream metadata source using AniBridge's transport policy."""

    url: str
    base_url: str
    _provider_data: dict[str, dict[str, str]] | None = field(
        default=None, init=False, repr=False
    )

    @property
    def provider_data(self) -> dict[str, dict[str, str]]:
        if self._provider_data is None:
            self._provider_data = fetch_episode_provider_data(
                url=self.url,
                base_url=self.base_url,
            )
        return self._provider_data

    def _normalize_language(self, language: str) -> str:
        available = list(self.provider_data)
        if language not in self.provider_data:
            raise LanguageUnavailableError(language, available)
        return language
