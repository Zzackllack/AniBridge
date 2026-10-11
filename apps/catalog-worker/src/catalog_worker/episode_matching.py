"""Source annotations are fallbacks, never edits to canonical title keys."""

import re

from catalog_core.identity import search_key

from .state import State

# AniWorld's demonstrated suffix. Keep other brackets and meaningful text.
FINALE = re.compile(r"\s*\[Final Episode\]\s*$", re.IGNORECASE)
EPISODE_ANNOTATION = re.compile(r"\s*\[Episode [0-9]{1,6}\]\s*$", re.IGNORECASE)


def source_keys(title: str, provider: str) -> tuple[str, ...]:
    if re.fullmatch(
        r"(?:folge|episode|episodio|ep)\s*[0-9]+", title.strip(), re.IGNORECASE
    ):
        return ()
    exact = search_key(title)
    stripped = (
        EPISODE_ANNOTATION.sub("", FINALE.sub("", title))
        if provider == "aniworld.to"
        else title
    )
    fallback = search_key(stripped)
    return (exact, fallback) if fallback and fallback != exact else (exact,)


def infer_seasons(state: State, tid: str) -> dict[int, int]:
    """Require three distinct unique name anchors, with no conflicting season.

    Provider numbers never enter the evidence. Reviewed correspondence is handled
    by the caller. Split seasons and cross-season repeated titles stay unresolved.
    """
    db = state.db
    evidence: dict[int, tuple[set[str], set[int]]] = {}
    for row in db.execute(
        "SELECT native_season,display_title FROM entity WHERE title_id=? AND kind='episode' AND display_title IS NOT NULL",
        (tid,),
    ):
        native, name = row
        anchors, seasons = evidence.setdefault(native, (set(), set()))
        for key in source_keys(name, state.provider):
            hints = db.execute(
                "SELECT season,episode FROM canonical_hint WHERE title_id=? AND title_key=? LIMIT 2",
                (tid, key),
            ).fetchall()
            if hints:
                if len(hints) == 1 and hints[0][1] is not None:
                    anchors.add(key)
                    seasons.add(hints[0][0])
                break
    proposed = {
        native: next(iter(seasons))
        for native, (anchors, seasons) in evidence.items()
        if len(anchors) >= 3 and len(seasons) == 1
    }
    # Two native seasons pointing to one canonical season need explicit review.
    return {
        native: season
        for native, season in proposed.items()
        if list(proposed.values()).count(season) == 1
    }
