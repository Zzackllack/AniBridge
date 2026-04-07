from __future__ import annotations

from typing import Optional

from app.config import CATALOG_SITE_CONFIGS


def default_languages_for_site(site: str) -> list[str]:
    """Return configured default languages for the given catalogue site."""
    cfg = CATALOG_SITE_CONFIGS.get(site)
    if cfg:
        languages = cfg.get("default_languages")
        if isinstance(languages, list) and languages:
            return list(languages)

    fallback = CATALOG_SITE_CONFIGS.get("aniworld.to", {}).get(
        "default_languages", ["German Dub", "German Sub", "English Sub"]
    )
    return list(fallback)


def coerce_positive_int(value: object) -> Optional[int]:
    """Coerce a value into a positive integer when possible."""
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except TypeError, ValueError:
        return None
    return parsed if parsed > 0 else None


def coerce_non_negative_int(value: object) -> Optional[int]:
    """Coerce a value into a non-negative integer when possible."""
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except TypeError, ValueError:
        return None
    return parsed if parsed >= 0 else None


def ordered_unique(values: list[str]) -> list[str]:
    """Return distinct non-empty strings while preserving input order."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = str(raw or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
