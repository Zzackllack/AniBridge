"""Source annotations are fallbacks, never edits to canonical title keys."""

import re
from collections import Counter, defaultdict

from catalog_core.identity import search_key

from .state import State

# AniWorld's demonstrated suffix. Keep other brackets and meaningful text.
FINALE = re.compile(r"\s*\[Final Episode\]\s*$", re.IGNORECASE)
EPISODE_ANNOTATION = re.compile(
    r"\s*\[(?:(?:JP|DE)\s+)?Episode [0-9]{1,6}\]\s*$", re.IGNORECASE
)
STO_WRAPPER = re.compile(r"^\((.+?)\s*/\s*Episode [0-9]{1,6}\)$", re.IGNORECASE)

# Only unambiguous English contractions. Possessive/'has'/'had' forms and
# semantic wording substitutions aren't normalization evidence.
CONTRACTIONS = {
    "i m": "i am",
    "you re": "you are",
    "we re": "we are",
    "they re": "they are",
    "i ll": "i will",
    "you ll": "you will",
    "we ll": "we will",
    "they ll": "they will",
    "don t": "do not",
    "doesn t": "does not",
    "didn t": "did not",
    "isn t": "is not",
    "aren t": "are not",
    "wasn t": "was not",
    "weren t": "were not",
    "won t": "will not",
    "can t": "cannot",
    "couldn t": "could not",
}
CONTRACTION_PATTERN = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(key) for key in CONTRACTIONS) + r")(?!\w)"
)


def contextual_key(key: str) -> str:
    """Candidate generation only; acceptance also requires independent anchors."""
    return CONTRACTION_PATTERN.sub(lambda match: CONTRACTIONS[match[0]], key)


def source_keys(title: str, provider: str) -> tuple[str, ...]:
    if re.fullmatch(
        r"(?:folge|episode|episodio|ep)\s*[0-9]+", title.strip(), re.IGNORECASE
    ):
        return ()
    exact = search_key(title)
    stripped = title
    if provider == "aniworld.to":
        stripped = EPISODE_ANNOTATION.sub("", FINALE.sub("", title))
    elif provider == "s.to" and (wrapper := STO_WRAPPER.fullmatch(title.strip())):
        # Observed season-row annotation. Keep arbitrary parentheses, part names
        # and other slash suffixes; these digits never provide map coordinates.
        stripped = wrapper[1]
    if re.fullmatch(r"(?:folge|episode|episodio|ep)\s*[0-9]+", search_key(stripped)):
        return ()
    fallback = search_key(stripped)
    return (exact, fallback) if fallback and fallback != exact else (exact,)


def infer_seasons(state: State, tid: str) -> dict[int, int]:
    """Require three distinct unique name anchors, with no conflicting season.

    Provider numbers never enter the evidence. Reviewed correspondence is handled
    by the caller. Split seasons and cross-season repeated titles stay unresolved.
    """
    db = state.db
    aliases = defaultdict(list)
    for eid, name in db.execute(
        "SELECT a.entity_id,a.display_title FROM entity_alias a JOIN entity e USING(entity_id) WHERE e.title_id=?",
        (tid,),
    ):
        aliases[eid].append(name)
    entities = []
    for eid, native, name in db.execute(
        "SELECT entity_id,native_season,display_title FROM entity WHERE title_id=? AND kind='episode'",
        (tid,),
    ):
        keys = {
            key
            for value in ([name] if name else []) + aliases[eid]
            for key in source_keys(value, state.provider)
            if key
        }
        entities.append((native, keys))
    counts = Counter(key for _, keys in entities for key in keys)
    hints = defaultdict(list)
    for key, season, episode in db.execute(
        "SELECT title_key,season,episode FROM canonical_hint WHERE title_id=?", (tid,)
    ):
        hints[key].append((season, episode))
    evidence: dict[int, tuple[set[tuple[int, int]], set[int]]] = {}
    for native, keys in entities:
        anchors, seasons = evidence.setdefault(native, (set(), set()))
        for key in keys:
            matches = hints[key]
            if len(matches) == 1 and matches[0][1] is not None and counts[key] == 1:
                # Several translated aliases of one episode are one anchor.
                anchors.add(matches[0])
                seasons.add(matches[0][0])
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
