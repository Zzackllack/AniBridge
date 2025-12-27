import re

from loguru import logger

_LANG_ALIASES = {
    "german": "German Dub",
    "ger": "German Dub",
    "gerdub": "German Dub",
    "dub": "German Dub",
    "germansub": "German Sub",
    "gersub": "German Sub",
    "subde": "German Sub",
    "de-sub": "German Sub",
    "englishsub": "English Sub",
    "engsub": "English Sub",
    "suben": "English Sub",
    "en-sub": "English Sub",
    "englishdub": "English Dub",
    "engdub": "English Dub",
    "duben": "English Dub",
    "en-dub": "English Dub",
    "endub": "English Dub",
}


def normalize_language(lang: str | None) -> str:
    """Normalize a language label (lang: Optional[str]) and return its canonical form."""
    if not lang:
        return "German Dub"
    cleaned = re.sub(r"[^a-z]", "", lang.lower())
    normalized = _LANG_ALIASES.get(cleaned, lang)
    logger.debug("Normalized language '{}' -> '{}'", lang, normalized)
    return normalized
