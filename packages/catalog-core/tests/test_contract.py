import base64
import json
import sqlite3
from pathlib import Path

import pytest

from catalog_core import artifact, fixtures, identity, magnet, manifest, schema
from catalog_core.json_codec import ContractError, dumps, loads


def test_identity_golden():
    title = identity.title_id("aniworld.to", "/anime/stream/example")
    entity = identity.entity_id(
        "aniworld.to", "/anime/stream/example/staffel-1/episode-2"
    )
    release = identity.release_id("aniworld.to", entity, "de-dub")
    assert title == "4b02f8e62ca7ae58ff7abfe4ca6e6a91c9b3e602e8e9f2b747cd07b7b4371e23"
    assert entity == "fe8964f7cc42e76e3301675ec46234048b7c87538d896de995eb873ff3271ba2"
    assert release == "ae735d09c7310ed45a6fa94d9193ffa7e80b741e84986366c6d133eb5ddc988b"
    assert (
        identity.infohash(release, "download")
        == "9faa798f6414ce25f3035566d891ed3fb27267dc"
    )
    assert (
        identity.infohash(release, "strm") == "6a9679b805403831a6087132b442543d0a656c55"
    )
    assert identity.digest("é") == identity.digest("e\u0301")
    assert identity.search_key("Ｓtraße: Élan!") == "strasse élan"
    assert len({identity.title_id(p, "/a") for p in identity.PROVIDERS}) == 3


@pytest.mark.parametrize(
    "value",
    [
        "/a/../b",
        "//evil/a",
        "/a%2fb",
        "/a%252fb",
        "/a%2eb",
        "/a?b",
        "/a#b",
        "/a\\b",
        "/a%00",
        "/a//b",
        "/a%zz",
    ],
)
def test_ambiguous_paths_rejected(value):
    with pytest.raises((ValueError, UnicodeError)):
        identity.path(value)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"x":1,"x":2}',
        b'{"x":1.0}',
        b'{"x":NaN}',
        b'{"x":9223372036854775808}',
        b'{"x":"\\ud800"}',
        b"[" * 10 + b"0" + b"]" * 10,
    ],
)
def test_strict_json(raw):
    with pytest.raises(ContractError):
        loads(raw)


@pytest.mark.parametrize("provider", sorted(identity.PROVIDERS))
@pytest.mark.parametrize("movie", [False, True])
def test_artifact_round_trip(tmp_path, provider, movie):
    compressed, payload, envelope, key = fixtures.build(tmp_path, provider, movie=movie)
    checked = manifest.verify(
        envelope, [key], "synthetic", provider, payload["published_at"]
    )
    assert checked.payload == payload
    restored = tmp_path / "restored.sqlite"
    artifact.decompress(compressed, restored, payload["artifact"])
    assert schema.validate(restored, payload) == payload["counts"]
    db = schema.connect(restored)
    title = dict(db.execute("SELECT * FROM title").fetchone())
    entity = dict(db.execute("SELECT * FROM entity").fetchone())
    release = dict(db.execute("SELECT * FROM release ORDER BY release_id").fetchone())
    db.close()
    grab = {
        "provider": provider,
        "title_id": title["title_id"],
        "entity_id": entity["entity_id"],
        "release_id": release["release_id"],
        "title_anchor": title["identity_anchor"],
        "entity_anchor": entity["identity_anchor"],
        "slug": title["slug"],
        "path": entity["path"],
        "kind": entity["kind"],
        "native_season": entity["native_season"],
        "native_episode": entity["native_episode"],
        "language": release["language"],
        "mode": "download",
        "canonical": None,
    }
    encoded = magnet.encode(grab, "Unknown quality")
    assert encoded.startswith(
        "magnet:?xt=urn:btih:"
        + identity.infohash(grab["release_id"], grab["mode"])
        + "&"
    )
    assert magnet.decode(encoded)[1:] == (grab, "Unknown quality")
    changed = dict(grab, mode="strm")
    assert magnet.decode(magnet.encode(changed, "x"))[0] != magnet.decode(encoded)[0]
    with pytest.raises(ContractError):
        magnet.decode(encoded + "&ab_v=2")


def test_signature_trust_floor_and_expiry(tmp_path):
    _, p, envelope, key = fixtures.build(tmp_path)
    for kwargs in (
        {"source_id": "wrong"},
        {"provider": "s.to"},
        {"keys": [bytes(32)]},
        {"now": p["expires_at"] + 301},
        {"accepted_revision": 2},
    ):
        args = {
            "keys": [key],
            "source_id": "synthetic",
            "provider": "aniworld.to",
            "now": p["published_at"],
        }
        args.update(kwargs)
        with pytest.raises(ContractError):
            manifest.verify(envelope, **args)
    accepted = manifest.verify(
        envelope, [key], "synthetic", "aniworld.to", p["published_at"]
    )
    manifest.verify(
        envelope, [key], "synthetic", "aniworld.to", p["expires_at"] + 10000, saved=True
    )
    manifest.verify(
        envelope,
        [key],
        "synthetic",
        "aniworld.to",
        p["published_at"],
        accepted_revision=1,
        accepted_digest=accepted.payload_digest,
    )
    with pytest.raises(ContractError):
        manifest.verify(
            envelope,
            [key],
            "synthetic",
            "aniworld.to",
            p["published_at"],
            accepted_revision=1,
            accepted_digest="0" * 64,
        )
    outer = json.loads(envelope)
    outer["signatures"][0]["sig"] = base64.b64encode(bytes(64)).decode()
    with pytest.raises(ContractError):
        manifest.verify(
            dumps(outer), [key], "synthetic", "aniworld.to", p["published_at"]
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "CREATE TABLE secret (value TEXT)",
        "CREATE VIEW hostile AS SELECT * FROM release",
        "CREATE TRIGGER hostile AFTER INSERT ON title BEGIN DELETE FROM release; END",
        "PRAGMA user_version=2",
        "UPDATE title SET search_key='wrong'",
        "UPDATE title SET detail_status='partial'",
        "DELETE FROM canonical_episode",
        "UPDATE canonical_episode SET entity_id='" + "0" * 64 + "'",
        "UPDATE release SET first_seen_at=first_seen_at+1,observed_at=observed_at+1000",
    ],
)
def test_schema_and_semantic_mutations(tmp_path, mutation):
    _, payload, _, _ = fixtures.build(tmp_path)
    db = sqlite3.connect(tmp_path / "fixture.sqlite")
    db.execute(mutation)
    db.commit()
    # Keep signed counts consistent so semantic mutants cannot pass solely
    # because the old count happens to differ after deletion.
    payload["counts"] = {
        table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in manifest.TABLE_LIMITS
    }
    db.close()
    with pytest.raises((ContractError, sqlite3.Error)):
        schema.validate(tmp_path / "fixture.sqlite", payload)


@pytest.mark.parametrize("change", ["trailing", "truncated", "overflow", "hash"])
def test_bad_compression(tmp_path, change):
    compressed, payload, _, _ = fixtures.build(tmp_path)
    meta = payload["artifact"].copy()
    if change in ("trailing", "truncated"):
        data = compressed.read_bytes()
        compressed.write_bytes(data + b"junk" if change == "trailing" else data[:-1])
        meta["size_bytes"] = compressed.stat().st_size
        meta["sha256"] = artifact.sha256(compressed)
    elif change == "overflow":
        meta["uncompressed_size_bytes"] = 1
    else:
        meta["sqlite_sha256"] = "0" * 64
    with pytest.raises(ContractError):
        artifact.decompress(compressed, tmp_path / "bad.sqlite", meta)


def test_deterministic_publication(tmp_path):
    a, pa, ea, _ = fixtures.build(tmp_path / "a")
    b, pb, eb, _ = fixtures.build(tmp_path / "b")
    assert a.read_bytes() == b.read_bytes()
    assert pa == pb and ea == eb


@pytest.mark.parametrize("version", [1, 2])
def test_frozen_artifact_and_signature_vector(tmp_path, version):
    vector = json.loads(
        (Path(__file__).parent / f"vectors/synthetic-v{version}.json").read_text()
    )
    envelope = manifest.unb64(vector["envelope"])
    key = manifest.unb64(vector["public_key"], 32)
    verified = manifest.verify(envelope, [key], "synthetic", "aniworld.to", 1800000000)
    compressed = tmp_path / "golden.sqlite.zst"
    compressed.write_bytes(manifest.unb64(vector["artifact"]))
    artifact.decompress(
        compressed, tmp_path / "golden.sqlite", verified.payload["artifact"]
    )
    assert schema.validate(tmp_path / "golden.sqlite", verified.payload)["release"] == 4


@pytest.mark.parametrize("version", [1, 2])
def test_validation_pager_is_bounded_without_changing_search_cache(
    tmp_path, monkeypatch, version
):
    _, payload, _, _ = fixtures.build(tmp_path / "fixture", schema_version=version)
    filename = tmp_path / "fixture/fixture.sqlite"
    original = schema.connect
    observed = []

    def checked(db, *args, **kwargs):
        observed.append(db.execute("PRAGMA cache_size").fetchone()[0])
        return original_definitions(db, *args, **kwargs)

    original_definitions = schema._validate_definitions
    monkeypatch.setattr(schema, "_validate_definitions", checked)
    assert schema.validate(filename, payload) == payload["counts"]
    assert observed == [-32768]
    db = original(filename)
    try:
        assert db.execute("PRAGMA cache_size").fetchone()[0] == -8192
    finally:
        db.close()
