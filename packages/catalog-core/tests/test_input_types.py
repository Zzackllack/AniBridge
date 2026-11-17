"""Malformed JSON types are contract errors even with a valid signature."""

import base64
import copy
import hashlib
from urllib.parse import urlencode

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog_core import fixtures, identity, magnet, manifest
from catalog_core.json_codec import ContractError, dumps

INVALID_VALUES = [None, True, "123", [], {}]


@pytest.mark.parametrize("value", INVALID_VALUES)
@pytest.mark.parametrize(
    "field",
    [
        "provider",
        "collection_state",
        "source_id",
        "coverage.details",
        "coverage.mappings",
        "counts.release",
        "artifact.size_bytes",
    ],
)
def test_validly_signed_manifest_rejects_wrong_json_types(tmp_path, value, field):
    _, payload, _, public = fixtures.build(tmp_path)
    keys = field.split(".")
    target = payload if len(keys) == 1 else payload[keys[0]]
    target[keys[-1]] = value
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    raw = dumps(payload)
    # Sign directly because a well-behaved publisher refuses malformed payloads.
    envelope = dumps(
        {
            "payload": manifest.b64(raw),
            "signatures": [
                {
                    "key_id": hashlib.sha256(public).hexdigest(),
                    "sig": manifest.b64(key.sign(raw)),
                }
            ],
        }
    )
    with pytest.raises(ContractError):
        manifest.verify(envelope, [public], "synthetic", "aniworld.to", 1800000000)


def episode_payload():
    title_anchor = "/anime/stream/example"
    entity_anchor = title_anchor + "/staffel-1/episode-2"
    entity = identity.entity_id("aniworld.to", entity_anchor)
    return {
        "provider": "aniworld.to",
        "title_id": identity.title_id("aniworld.to", title_anchor),
        "entity_id": entity,
        "release_id": identity.release_id("aniworld.to", entity, "de-dub"),
        "title_anchor": title_anchor,
        "entity_anchor": entity_anchor,
        "slug": "example",
        "path": entity_anchor,
        "kind": "episode",
        "native_season": 1,
        "native_episode": 2,
        "language": "de-dub",
        "mode": "download",
        "canonical": {
            "namespace": "tvdb",
            "external_id": "123",
            "season": 0,
            "episode": 1,
        },
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("native_season", 2**31),
        ("native_episode", 2**31),
        ("canonical.season", 2**31),
        ("canonical.episode", 2**31),
    ],
)
def test_grab_coordinates_match_the_wire_bounds(field, value):
    payload = copy.deepcopy(episode_payload())
    target = payload if "." not in field else payload[field.split(".")[0]]
    target[field.split(".")[-1]] = value
    with pytest.raises(ContractError):
        magnet.validate(payload)


@pytest.mark.parametrize("field", ["native_season", "canonical.season"])
def test_grab_coordinate_maximum_is_still_accepted(field):
    payload = copy.deepcopy(episode_payload())
    target = payload if "." not in field else payload[field.split(".")[0]]
    target[field.split(".")[-1]] = 2**31 - 1
    magnet.validate(payload)


@pytest.mark.parametrize("value", INVALID_VALUES)
@pytest.mark.parametrize(
    "field", ["provider", "language", "mode", "kind", "canonical.namespace"]
)
def test_malformed_grab_type_rejects_before_http_admission(value, field):
    original = episode_payload()
    magnet.validate(original)
    payload = copy.deepcopy(original)
    keys = field.split(".")
    target = payload if len(keys) == 1 else payload[keys[0]]
    target[keys[-1]] = value
    raw = base64.urlsafe_b64encode(dumps(payload)).decode().rstrip("=")
    encoded = "magnet:?" + urlencode(
        {
            "xt": "urn:btih:" + identity.infohash(original["release_id"], "download"),
            "dn": "Unknown",
            "ab_v": "2",
            "ab_data": raw,
        },
        safe=":",
    )
    with pytest.raises(ContractError):
        magnet.decode(encoded)
