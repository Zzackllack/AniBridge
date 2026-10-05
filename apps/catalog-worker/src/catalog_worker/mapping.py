"""Conservative canonical matching. Number equality never maps an episode."""

from dataclasses import dataclass

from catalog_core.identity import search_key, validate_external_id


@dataclass(frozen=True)
class CanonicalTitle:
    namespace: str
    external_id: str
    titles: tuple[str, ...]
    year: int | None
    kind: str


@dataclass(frozen=True)
class CanonicalEpisode:
    season: int
    episode: int
    title: str
    external_id: str | None = None


def match_title(
    names: tuple[str, ...],
    year: int | None,
    kind: str,
    candidates: tuple[CanonicalTitle, ...],
    explicit_id: tuple[str, str] | None = None,
) -> tuple[CanonicalTitle, str] | None:
    keys = {search_key(name) for name in names if search_key(name)}
    matches = []
    for candidate in candidates:
        validate_external_id(candidate.namespace, candidate.external_id)
        if kind != candidate.kind:
            continue
        if explicit_id:
            if (candidate.namespace, candidate.external_id) == explicit_id:
                matches.append((candidate, "explicit_id"))
        elif (
            year is not None
            and candidate.year == year
            and keys.intersection(search_key(n) for n in candidate.titles)
        ):
            matches.append((candidate, "exact_title_year"))
    unique = {
        (candidate.namespace, candidate.external_id): (candidate, evidence)
        for candidate, evidence in matches
    }
    return next(iter(unique.values())) if len(unique) == 1 else None


def match_episode(
    title: str | None,
    native_season: int,
    candidates: tuple[CanonicalEpisode, ...],
    proven_season_map: dict[int, int],
) -> CanonicalEpisode | None:
    if title is None or native_season not in proven_season_map:
        return None
    key = search_key(title)
    matches = [
        episode
        for episode in candidates
        if key
        and episode.season == proven_season_map[native_season]
        and search_key(episode.title) == key
    ]
    return matches[0] if len(matches) == 1 else None
