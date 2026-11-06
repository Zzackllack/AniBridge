"""Only explicit local probe fields may become quality evidence."""

import hashlib

from catalog_core.json_codec import dumps

EXTRACTOR_VERSION = "aniworld-voe-prefix-1"


def valid_record(record: object) -> bool:
    """Reject damaged private cache rows before they can affect a response."""
    if type(record) is not dict or record.get("outcome") not in (
        "ok",
        "unknown",
        "challenge",
    ):
        return False
    if "inherit" in record and type(record["inherit"]) is not bool:
        return False
    if (
        not all(
            type(record.get(key)) is str and 0 < len(record[key]) <= maximum
            for key, maximum in (
                ("entity_id", 128),
                ("path", 2048),
                ("scope", 64),
                ("snapshot", 64),
            )
        )
        or type(record.get("measured_at")) is not int
    ):
        return False
    if record["outcome"] != "ok":
        return True
    codec = record.get("codec")
    return (
        type(record.get("height")) is int
        and 1 <= record["height"] <= 16384
        and (
            codec is None or type(codec) is str and len(codec) <= 32 and codec.isalnum()
        )
        and all(
            type(record.get(key)) is str and 0 < len(record[key]) <= 64
            for key in ("host", "variant")
        )
    )


def measured(probe: dict, host: str) -> dict | None:
    streams = probe.get("streams", [])
    if (
        type(streams) is not list
        or len(streams) > 32
        or not all(type(stream) is dict for stream in streams)
    ):
        return None
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    if len(videos) != 1:
        return None
    height, codec = videos[0].get("height"), videos[0].get("codec_name")
    if type(height) is not int or not 1 <= height <= 16384:
        return None
    codec = (
        codec if type(codec) is str and len(codec) <= 32 and codec.isalnum() else None
    )
    return {
        "height": height,
        "codec": codec,
        "host": host,
        "variant": hashlib.sha256(
            dumps([host, videos[0].get("width"), height, codec])
        ).hexdigest(),
    }
