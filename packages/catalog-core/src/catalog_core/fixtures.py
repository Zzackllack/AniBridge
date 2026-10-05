"""Synthetic protocol fixtures. Never uses a real provider or a production key."""

from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from . import artifact, identity, schema
from .compact import Writer
from .manifest import TABLE_LIMITS, sign


def build(
    directory: Path,
    provider: str = "aniworld.to",
    revision: int = 1,
    now: int = 1800000000,
    *,
    movie: bool = False,
    schema_version: int = 1,
) -> tuple[Path, dict, bytes, bytes]:
    directory.mkdir(parents=True, exist_ok=True)
    db_path = directory / "fixture.sqlite"
    title_path = "/anime/stream/example"
    entity_path = title_path if movie else title_path + "/staffel-1/episode-2"
    title_id = identity.title_id(provider, title_path)
    entity_id = identity.entity_id(provider, entity_path)
    namespace = "tmdb-movie" if movie else "tvdb"
    mapping_id = identity.mapping_id(provider, title_id, namespace, "123")
    db = schema.create(db_path, version=schema_version)
    writer = Writer(db, schema_version)
    with db:
        writer.insert("catalog", (1, provider, schema_version, 1, now))
        writer.insert(
            "title",
            (
                title_id,
                title_path,
                "example",
                "Example",
                "example",
                "movie" if movie else "series",
                2020,
                title_path,
                now,
                "complete",
            ),
        )
        writer.insert(
            "entity",
            (
                entity_id,
                title_id,
                entity_path,
                "movie" if movie else "episode",
                None if movie else 1,
                None if movie else 2,
                "Second",
                entity_path,
                now,
            ),
        )
        for language in sorted(identity.LANGUAGES):
            writer.insert(
                "release",
                (
                    identity.release_id(provider, entity_id, language),
                    entity_id,
                    language,
                    now,
                    now,
                ),
            )
        writer.insert(
            "canonical_title",
            (mapping_id, title_id, namespace, "123", "synthetic-v1", "reviewed", now),
        )
        if not movie:
            writer.insert(
                "canonical_episode",
                (mapping_id, entity_id, 0, 1, None, "reviewed", now),
            )
    counts = {
        t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLE_LIMITS
    }
    db.close()
    compressed = directory / "fixture.sqlite.zst"
    metadata = artifact.compress(db_path, compressed)
    payload = {
        "protocol_version": 1,
        "catalog_schema_version": schema_version,
        "identity_version": 1,
        "source_id": "synthetic",
        "provider": provider,
        "revision": revision,
        "published_at": now,
        "expires_at": now + 172800,
        "listing_checked_at": now,
        "oldest_active_check_at": now,
        "collection_state": "healthy",
        "coverage": {
            "titles": "complete",
            "details": "complete",
            "mappings": "complete",
        },
        "counts": counts,
        "artifact": metadata,
    }
    schema.validate(db_path, payload)
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    return (
        compressed,
        payload,
        sign(payload, [key]),
        key.public_key().public_bytes_raw(),
    )
