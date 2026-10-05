"""Hash verified local bytes in a bounded child for interrupted completion reuse."""

import argparse
import hashlib
from pathlib import Path

from catalog_core.files import atomic_write
from catalog_core.json_codec import dumps, loads, require
from catalog_core.supervisor import limit_child


def fingerprint(payload: dict) -> str:
    frozen = {key: value for key, value in payload.items() if key != "generation"}
    return hashlib.sha256(dumps(frozen)).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("write", "verify"))
    parser.add_argument("root", type=Path)
    parser.add_argument("media", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("fingerprint")
    args = parser.parse_args()
    limit_child()
    root = args.root.resolve()
    require(
        not args.media.is_symlink()
        and args.media.resolve().is_relative_to(root)
        and args.media.is_file()
        and not args.receipt.is_symlink()
        and args.receipt.resolve().is_relative_to(root),
        "invalid output ownership",
    )
    with args.media.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    record = {
        "request": args.fingerprint,
        "sha256": digest,
        "size": args.media.stat().st_size,
    }
    require(record["size"] > 0, "empty output")
    if args.operation == "write":
        atomic_write(args.receipt, dumps(record))
    else:
        require(args.receipt.stat().st_size <= 4096, "invalid receipt")
        require(loads(args.receipt.read_bytes(), 4096) == record, "output changed")


if __name__ == "__main__":
    main()
