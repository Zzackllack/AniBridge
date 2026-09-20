from importlib import import_module
from typing import TYPE_CHECKING, Any

from app.utils.logger import config as configure_logger

configure_logger()

if TYPE_CHECKING:
    from .download import download_episode
    from .episode import build_episode
    from .errors import DownloadError, LanguageUnavailableError
    from .provider_resolution import get_direct_url_with_fallback
    from .types import Host, Language, ProgressCb, Provider


_LAZY_EXPORTS = {
    "download_episode": ("app.core.downloader.download", "download_episode"),
    "build_episode": ("app.core.downloader.episode", "build_episode"),
    "DownloadError": ("app.core.downloader.errors", "DownloadError"),
    "LanguageUnavailableError": (
        "app.core.downloader.errors",
        "LanguageUnavailableError",
    ),
    "get_direct_url_with_fallback": (
        "app.core.downloader.provider_resolution",
        "get_direct_url_with_fallback",
    ),
    "Host": ("app.core.downloader.types", "Host"),
    "Language": ("app.core.downloader.types", "Language"),
    "Provider": ("app.core.downloader.types", "Provider"),
    "ProgressCb": ("app.core.downloader.types", "ProgressCb"),
}


def __getattr__(name: str) -> Any:
    """Load public facade members without importing the complete runtime graph."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


__all__ = [
    "DownloadError",
    "LanguageUnavailableError",
    "Host",
    "Language",
    "Provider",
    "ProgressCb",
    "build_episode",
    "get_direct_url_with_fallback",
    "download_episode",
]
