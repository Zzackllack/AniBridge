"""Bounded decoder/validator executable, with no API or worker imports."""

import argparse
from pathlib import Path

from . import artifact, schema
from .json_codec import loads, require
from .supervisor import limit_child


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["decompress", "validate", "saved"])
    parser.add_argument("source", type=Path)
    parser.add_argument("payload", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--compressed-cap", type=int, default=256 * 1024**2)
    parser.add_argument("--sqlite-cap", type=int, default=1024**3)
    args = parser.parse_args()
    limit_child(output_bytes=args.sqlite_cap)
    payload = loads(args.payload.read_bytes())
    if args.operation == "decompress":
        artifact.decompress(
            args.source,
            args.destination,
            payload["artifact"],
            args.compressed_cap,
            args.sqlite_cap,
        )
    elif args.operation == "saved":
        # Only for a committed, previously validated version. Matching every
        # byte against its signed digest preserves that validation across a
        # restart without repeating all identity joins for unchanged bytes.
        require(
            args.source.stat().st_size
            == payload["artifact"]["uncompressed_size_bytes"],
            "corrupt_active",
        )
        require(
            artifact.sha256(args.source) == payload["artifact"]["sqlite_sha256"],
            "corrupt_active",
        )
    else:
        schema.validate(args.source, payload)


if __name__ == "__main__":
    main()
