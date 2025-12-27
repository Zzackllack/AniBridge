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
    """
    Normalize a language identifier to a canonical label.
    
    If `lang` is falsy (None or empty) this returns "German Dub". For non-empty input, common shorthand and variant forms are mapped to canonical labels (e.g., "German Dub", "German Sub", "English Sub", "English Dub"); if no mapping exists the original `lang` value is returned.
    
    Parameters:
        lang (str | None): Language identifier to normalize. May be None or an empty string.
    
    Returns:
        str: The canonical language label for known variants, or the original `lang` value when no canonical mapping is found.
    """
    if not lang:
        return "German Dub"
    cleaned = re.sub(r"[^a-z]", "", lang.lower())
    normalized = _LANG_ALIASES.get(cleaned, lang)
    logger.debug("Normalized language '%s' -> '%s'", lang, normalized)
    return normalized