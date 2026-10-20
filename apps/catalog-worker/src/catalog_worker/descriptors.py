"""Compact multilingual episode evidence, joined by canonical IDs, never positions."""

import hashlib
import json
from dataclasses import asdict

from catalog_core.json_codec import dumps, require

from .canonical_failures import verify
from .mapping import CanonicalEpisode
from .parent_evidence import compact
from .state import State

CODEC = 1


def episode_identity(row: dict, parent: int) -> int:
    """Accept either explicit TVDB pair; mixed or conflicting pairs are unsafe.

    Some v2 Skyhook responses still contain v1 episode field names. The top-level
    namespace alone cannot bind an episode: its own explicit parent must agree.
    """
    pairs = []
    for id_key, parent_key in (
        ("metadataId", "metadataShowId"),
        ("tvdbId", "tvdbShowId"),
    ):
        if id_key not in row and parent_key not in row:
            continue
        eid, show = row.get(id_key), row.get(parent_key)
        verify(
            type(eid) is int and eid > 0 and type(show) is int and show > 0,
            "episode_identity_missing",
            "incomplete canonical episode identity",
        )
        verify(show == parent, "episode_parent_conflict", "canonical parent mismatch")
        pairs.append(eid)
    verify(
        bool(pairs), "episode_identity_missing", "missing canonical episode identity"
    )
    verify(
        len(set(pairs)) == 1,
        "episode_identity_conflict",
        "conflicting canonical episode identity",
    )
    return pairs[0]


def episodes(payload: dict) -> list[CanonicalEpisode]:
    rows = payload.get("episodes") or []
    require(
        isinstance(rows, list) and len(rows) <= 100000, "invalid canonical episode list"
    )
    result = []
    coordinates, identities = {}, {}
    for row in rows:
        require(isinstance(row, dict), "invalid canonical episode")
        season, number, name, eid = (
            row.get(key) for key in ("seasonNumber", "episodeNumber", "title", "tvdbId")
        )
        if payload.get("metadataSource") == "tvdb":
            eid = episode_identity(row, payload["tvdbId"])
        if name is None and type(eid) is int and eid > 0:
            # An untranslated English row still carries a canonical ID/order.
            # Keep that identity so a verified German name can join it later.
            name = ""
        if (
            type(season) is not int
            or season < 0
            or type(number) is not int
            or number <= 0
            or not isinstance(name, str)
            or len(name.encode()) > 512
        ):
            continue
        verify(
            row.get("tvdbShowId", payload["tvdbId"]) == payload["tvdbId"],
            "episode_parent_conflict",
            "canonical parent mismatch",
        )
        coordinate = (season, number)
        signature = (eid, name)
        verify(
            coordinate not in coordinates or coordinates[coordinate] == signature,
            "episode_coordinate_conflict",
            "conflicting canonical episode coordinate",
        )
        verify(
            not eid or eid not in identities or identities[eid] == coordinate,
            "episode_identity_conflict",
            "conflicting canonical episode identity",
        )
        if coordinate in coordinates:
            continue
        coordinates[coordinate] = signature
        if eid:
            identities[eid] = coordinate
        result.append(
            CanonicalEpisode(
                season, number, name, str(eid) if type(eid) is int and eid > 0 else None
            )
        )
    return result


def merge(
    primary: list[CanonicalEpisode], translated: list[CanonicalEpisode]
) -> list[CanonicalEpisode]:
    """Only identical episode IDs AND coordinates can contribute translated names."""
    translations = {}
    for row in translated:
        if row.external_id and row.title:
            key = (row.external_id, row.season, row.episode)
            translations.setdefault(key, set()).add(row.title)
    return [
        CanonicalEpisode(
            row.season,
            row.episode,
            row.title,
            row.external_id,
            tuple(
                sorted(
                    translations.get((row.external_id, row.season, row.episode), set())
                    - {row.title}
                )
            ),
        )
        for row in primary
    ]


def translation(
    payload: object, external: str, language: str
) -> tuple[list[CanonicalEpisode], bool]:
    """An explicitly empty translation cannot invalidate useful primary names.

    Skyhook may omit its language tag when every translated episode title is
    null. Validate identities first; never consume a named but untagged response.
    """
    verify(
        isinstance(payload, dict)
        and payload.get("metadataSource") == "tvdb"
        and str(payload.get("tvdbId")) == external,
        "translation_identity_conflict",
        "canonical translation identity mismatch",
    )
    rows = episodes(payload)
    missing = payload.get("language") is None and all(not row.title for row in rows)
    verify(
        payload.get("language") == language or missing,
        "translation_identity_conflict",
        "canonical translation language mismatch",
    )
    # Check the original rows too: ignored malformed coordinates cannot conceal
    # named data whose language was never established.
    if missing:
        verify(
            all(
                row.get("title") in (None, "") for row in payload.get("episodes") or []
            ),
            "translation_identity_conflict",
            "untagged canonical translation names",
        )
        return [], True
    return rows, False


def save(
    state: State,
    external: str,
    details: dict,
    rows: list[CanonicalEpisode],
    now: int,
    delay: int,
) -> None:
    payload = dumps(
        {
            "tvdbId": int(external),
            "imdbId": details.get("imdbId"),
            "tmdbId": details.get("tmdbId"),
            "parent": details.get("parent") or compact(details),
            # These are checked language requests. Empty optional translations
            # are recorded separately and provide no positive name evidence.
            "languages": details.get("_episode_languages", []),
            "missing_languages": details.get(
                "_missing_episode_languages", details.get("missing_languages", [])
            ),
            "api": details.get("api")
            or (
                "skyhook-v2"
                if details.get("metadataSource") == "tvdb"
                else "skyhook-v1"
            ),
            "codec": CODEC,
            "episodes": [asdict(row) for row in rows],
        }
    )
    require(len(payload) <= 8 * 1024**2, "compact descriptor limit")
    state.db.execute(
        "INSERT INTO canonical_descriptor VALUES(?,?,?,?,?) ON CONFLICT(external_id) DO UPDATE SET content_hash=excluded.content_hash,payload=excluded.payload,acquired_at=excluded.acquired_at,next_due=excluded.next_due",
        (
            external,
            hashlib.sha256(payload).hexdigest(),
            payload.decode(),
            now,
            now + delay,
        ),
    )


def cached(
    states: list[State],
    external: str,
    now: int,
    imdb: str | None,
    languages: tuple[str, ...] = (),
    *,
    newer_than: int | None = None,
) -> tuple[dict, list[CanonicalEpisode], int, int] | None:
    """Bounded single-ID lookups; source/provider identities are never shared."""
    for state in states:
        row = state.db.execute(
            "SELECT payload,acquired_at,next_due FROM canonical_descriptor WHERE external_id=? AND next_due>?",
            (external, now),
        ).fetchone()
        if row:
            # A retry can reuse verified evidence acquired after its failure,
            # including another provider's. Older evidence cannot prove recovery.
            if newer_than is not None and row[1] <= newer_than:
                continue
            data = json.loads(row[0])
            if data.get("codec") != CODEC:
                continue
            if imdb and data.get("imdbId") != imdb:
                continue
            if not set(languages).issubset(data.get("languages", [])):
                continue
            records = [
                CanonicalEpisode(
                    e["season"],
                    e["episode"],
                    e["title"],
                    e["external_id"],
                    tuple(e["aliases"]),
                )
                for e in data["episodes"]
            ]
            return data, records, row[1], row[2]
    return None
