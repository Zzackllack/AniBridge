"""A shared IMDb ID can span edited series cuts; retain conflicting associations."""

import json

from catalog_core.json_codec import require

from .mapping import CanonicalTitle, match_title
from .state import State


def valid(parent: object) -> bool:
    """A missing or damaged private proof needs fresh evidence, never a guess."""
    if not isinstance(parent, dict) or set(parent) != {"names", "year", "imdb"}:
        return False
    names, year, imdb = (parent[key] for key in ("names", "year", "imdb"))
    try:
        return (
            isinstance(names, list)
            # Compact metadata contributes at most 302 names, plus the
            # separately ID-verified search title and its 100 aliases.
            and 1 <= len(names) <= 403
            and all(
                isinstance(name, str) and len(name.encode()) <= 512 for name in names
            )
            and (year is None or type(year) is int and 1800 <= year <= 2200)
            and (imdb is None or isinstance(imdb, str) and len(imdb.encode()) <= 32)
        )
    except UnicodeError:
        return False


def compact(payload: dict) -> dict:
    names = [payload.get("title")]
    if payload.get("originalTitle"):
        names.append(payload["originalTitle"])
    for field in ("aliases", "alternativeTitles", "translations"):
        rows = payload.get(field) or []
        require(
            isinstance(rows, list) and len(rows) <= 100,
            "invalid canonical parent aliases",
        )
        for row in rows:
            name = row.get("title") if isinstance(row, dict) else row
            if isinstance(name, str):
                names.append(name)
    require(
        all(isinstance(name, str) and len(name.encode()) <= 512 for name in names),
        "invalid canonical parent names",
    )
    raw = payload.get("firstAired") or ""
    year = payload.get("year")
    if year is None and isinstance(raw, str) and raw[:4].isdecimal():
        year = int(raw[:4])
    require(
        year is None or type(year) is int and 1800 <= year <= 2200,
        "invalid canonical parent year",
    )
    return {
        "names": list(dict.fromkeys(names)),
        "year": year,
        "imdb": payload.get("imdbId"),
    }


def check(state: State, tid: str, external: str, parent: dict) -> str:
    row = state.db.execute(
        "SELECT t.display_title,t.year,m.explicit_imdb FROM title t LEFT JOIN mapping_input m USING(title_id) WHERE t.title_id=?",
        (tid,),
    ).fetchone()
    if not row:
        return "waiting_parent_verification"
    name, year, imdb = row
    if year is not None and parent["year"] is not None and year != parent["year"]:
        return "parent_conflict"
    if imdb:
        return "verified" if imdb == parent["imdb"] else "parent_conflict"
    aliases = tuple(
        r[0]
        for r in state.db.execute(
            "SELECT display_alias FROM alias WHERE title_id=? ORDER BY search_key",
            (tid,),
        )
    )
    candidate = CanonicalTitle(
        "tvdb", external, tuple(parent["names"]), parent["year"], "series"
    )
    return (
        "verified"
        if match_title((name, *aliases), year, "series", (candidate,))
        else "waiting_parent_verification"
    )


def status(state: State, tid: str, external: str, evidence: str) -> str:
    if evidence == "reviewed":
        return "verified"
    if not state.db.execute(
        "SELECT 1 FROM sqlite_schema WHERE name='canonical_descriptor'"
    ).fetchone():
        return "waiting_parent_verification"
    row = state.db.execute(
        "SELECT json_extract(payload,'$.parent') FROM canonical_descriptor WHERE external_id=?",
        (external,),
    ).fetchone()
    if not row or not row[0]:
        return "waiting_parent_verification"
    parent = json.loads(row[0])
    return (
        check(state, tid, external, parent)
        if valid(parent)
        else "waiting_parent_verification"
    )
