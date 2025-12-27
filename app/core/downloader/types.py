"""Type aliases describing downloader inputs and callbacks."""

from typing import Callable, Literal

# Supported human-readable language labels.
Language = Literal["German Dub", "German Sub", "English Sub", "English Dub"]
# Supported provider identifiers in resolver order.
Provider = Literal[
    "VOE",
    "Vidoza",
    "Doodstream",
    "Filemoon",
    "Vidmoly",
    "Streamtape",
    "LoadX",
    "SpeedFiles",
    "Luluvdo",
]
# Callback invoked with yt-dlp progress dictionaries.
ProgressCb = Callable[[dict], None]
