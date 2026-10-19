"""Signed catalog metadata. The unsigned pointer is only a bounded hint."""

import base64
import binascii
import hashlib
import re
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .identity import PROVIDERS
from .json_codec import ContractError, dumps, fields, integer, loads, require

TABLE_LIMITS = {
    "title": 100000,
    "alias": 1000000,
    "entity": 2000000,
    "release": 8000000,
    "canonical_title": 400000,
    "canonical_episode": 8000000,
    "identity_alias": 2000000,
}
STATES = {
    "healthy",
    "partial",
    "blocked",
    "transport_error",
    "parser_error",
    "publishing_error",
    "clock_error",
}


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def unb64(value: object, length: int | None = None) -> bytes:
    require(type(value) is str, "invalid base64")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ContractError("invalid base64") from exc
    require(b64(decoded) == value, "noncanonical base64")
    require(length is None or len(decoded) == length, "invalid decoded length")
    return decoded


def hex_digest(value: object) -> str:
    require(
        type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        "invalid digest",
    )
    return value


def validate_payload(p: dict) -> dict:
    fields(
        p,
        {
            "protocol_version",
            "catalog_schema_version",
            "identity_version",
            "source_id",
            "provider",
            "revision",
            "published_at",
            "expires_at",
            "listing_checked_at",
            "oldest_active_check_at",
            "collection_state",
            "coverage",
            "counts",
            "artifact",
        },
    )
    for name in ("protocol_version", "identity_version"):
        integer(p[name], 1, 1)
    integer(p["catalog_schema_version"], 1, 2)
    require(
        type(p["source_id"]) is str
        and re.fullmatch(r"[a-z0-9._-]{1,64}", p["source_id"]) is not None,
        "invalid source ID",
    )
    require(
        type(p["provider"]) is str and p["provider"] in PROVIDERS, "unknown provider"
    )
    integer(p["revision"], 1)
    for name in ("published_at", "expires_at", "listing_checked_at"):
        integer(p[name])
    if p["oldest_active_check_at"] is not None:
        integer(p["oldest_active_check_at"])
        require(
            p["oldest_active_check_at"] <= p["published_at"] + 300, "future observation"
        )
    require(p["listing_checked_at"] <= p["published_at"] + 300, "future listing")
    require(p["expires_at"] == p["published_at"] + 172800, "invalid expiry")
    require(
        type(p["collection_state"]) is str and p["collection_state"] in STATES,
        "unknown collection state",
    )
    coverage = fields(p["coverage"], {"titles", "details", "mappings"})
    require(coverage["titles"] == "complete", "incomplete listing")
    require(
        all(
            type(coverage[k]) is str and coverage[k] in {"partial", "complete"}
            for k in ("details", "mappings")
        ),
        "invalid coverage",
    )
    counts = fields(p["counts"], set(TABLE_LIMITS))
    for table, maximum in TABLE_LIMITS.items():
        integer(counts[table], 0, maximum)
    artifact = fields(
        p["artifact"],
        {"sha256", "sqlite_sha256", "size_bytes", "uncompressed_size_bytes"},
    )
    for key in ("sha256", "sqlite_sha256"):
        hex_digest(artifact[key])
    for key in ("size_bytes", "uncompressed_size_bytes"):
        integer(artifact[key], 1)
    return p


@dataclass(frozen=True)
class VerifiedManifest:
    payload: dict
    payload_digest: str
    envelope: bytes


def verify(
    envelope: bytes,
    keys: list[bytes],
    source_id: str,
    provider: str,
    now: int,
    *,
    accepted_revision: int = 0,
    accepted_digest: str | None = None,
    last_publication: int = 0,
    saved: bool = False,
) -> VerifiedManifest:
    outer = fields(loads(envelope, 65536), {"payload", "signatures"})
    payload_bytes = unb64(outer["payload"])
    require(len(payload_bytes) <= 32768, "payload too large")
    signatures = outer["signatures"]
    require(
        type(signatures) is list and 1 <= len(signatures) <= 4, "invalid signatures"
    )
    trusted = {
        hashlib.sha256(k).hexdigest(): Ed25519PublicKey.from_public_bytes(k)
        for k in keys
    }
    seen, valid = set(), False
    for signature in signatures:
        fields(signature, {"key_id", "sig"})
        key_id = hex_digest(signature["key_id"])
        require(key_id not in seen, "duplicate signing key")
        seen.add(key_id)
        raw = unb64(signature["sig"], 64)
        if key_id in trusted:
            try:
                trusted[key_id].verify(raw, payload_bytes)
                valid = True
            except InvalidSignature:
                pass
    require(valid, "untrusted signature")
    p = validate_payload(loads(payload_bytes))
    require(
        p["source_id"] == source_id and p["provider"] == provider,
        "wrong source/provider",
    )
    digest = hashlib.sha256(payload_bytes).hexdigest()
    if not saved:
        require(
            p["published_at"] <= now + 300 and p["expires_at"] >= now - 300,
            "expired/future publication",
        )
        require(
            p["published_at"] >= last_publication - 300, "publication clock rollback"
        )
        require(p["revision"] >= accepted_revision, "revision rollback")
        if p["revision"] == accepted_revision:
            require(digest == accepted_digest, "revision equivocation")
    return VerifiedManifest(p, digest, envelope)


def sign(payload: dict, keys: list[Ed25519PrivateKey]) -> bytes:
    raw = dumps(validate_payload(payload))
    require(1 <= len(keys) <= 4, "invalid signing key count")
    result = dumps(
        {
            "payload": b64(raw),
            "signatures": [
                {
                    "key_id": hashlib.sha256(
                        key.public_key().public_bytes_raw()
                    ).hexdigest(),
                    "sig": b64(key.sign(raw)),
                }
                for key in keys
            ],
        }
    )
    # Publishers use exactly the same parser as readers.
    verify(
        result,
        [k.public_key().public_bytes_raw() for k in keys],
        payload["source_id"],
        payload["provider"],
        payload["published_at"],
    )
    return result


def pointer(data: bytes) -> int:
    obj = fields(loads(data, 4096), {"protocol_version", "revision"})
    integer(obj["protocol_version"], 1, 1)
    return integer(obj["revision"], 1)
