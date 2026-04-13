"""Type aliases describing downloader inputs and callbacks."""

from typing import Callable, Literal

# Supported human-readable language labels.
Language = Literal["German Dub", "German Sub", "English Sub", "English Dub"]
# Supported direct video-host identifiers in resolver order.
Host = Literal[
    "VOE",
    "Vidoza",
    "Doodstream",
    "Filemoon",
    "Vidmoly",
    "Streamtape",
    "LoadX",
    "Luluvdo",
]
# Backwards-compatible alias used by older downloader call sites.
Provider = Host
# Callback invoked with yt-dlp progress dictionaries.
ProgressCb = Callable[[dict], None]
