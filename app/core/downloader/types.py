from typing import Callable, Literal

Language = Literal["German Dub", "German Sub", "English Sub", "English Dub"]
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
ProgressCb = Callable[[dict], None]
