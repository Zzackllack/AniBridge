"""Streaming single-frame zstd; callers supervise CPU/memory and wall time."""

import hashlib
import os
from pathlib import Path

from compression import zstd

from .json_codec import require

CHUNK = 65536


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def compress(source: Path, destination: Path) -> dict:
    encoder = zstd.ZstdCompressor(
        options={
            zstd.CompressionParameter.window_log: 26,
            zstd.CompressionParameter.compression_level: 3,
        }
    )
    with source.open("rb") as src, destination.open("xb") as dst:
        while chunk := src.read(CHUNK):
            dst.write(encoder.compress(chunk))
        dst.write(encoder.flush())
        dst.flush()
        os.fsync(dst.fileno())
    return {
        "sha256": sha256(destination),
        "sqlite_sha256": sha256(source),
        "size_bytes": destination.stat().st_size,
        "uncompressed_size_bytes": source.stat().st_size,
    }


def decompress(
    source: Path,
    destination: Path,
    metadata: dict,
    compressed_cap: int = 256 * 1024**2,
    sqlite_cap: int = 1024**3,
) -> None:
    require(
        source.stat().st_size == metadata["size_bytes"] <= compressed_cap,
        "compressed size mismatch",
    )
    require(sha256(source) == metadata["sha256"], "compressed digest mismatch")
    require(0 < metadata["uncompressed_size_bytes"] <= sqlite_cap, "SQLite too large")
    decoder = zstd.ZstdDecompressor(
        options={zstd.DecompressionParameter.window_log_max: 26}
    )
    written = 0
    with source.open("rb") as src, destination.open("xb") as dst:
        while not decoder.eof:
            chunk = src.read(CHUNK) if decoder.needs_input else b""
            require(chunk or not decoder.needs_input, "truncated zstd")
            output = decoder.decompress(chunk, max_length=CHUNK)
            written += len(output)
            require(
                written <= metadata["uncompressed_size_bytes"], "decompression overflow"
            )
            dst.write(output)
        require(
            not decoder.unused_data and not src.read(1), "multiple frames/trailing data"
        )
        require(
            written == metadata["uncompressed_size_bytes"], "decompressed size mismatch"
        )
        dst.flush()
        os.fsync(dst.fileno())
    require(sha256(destination) == metadata["sqlite_sha256"], "SQLite digest mismatch")
