"""Artifact publication is atomic, exclusive and leaves no partial target."""

import pytest

from catalog_core import artifact, fixtures
from catalog_core.json_codec import ContractError


def temporary_files(directory):
    return sorted(
        path.name for path in directory.iterdir() if path.name.startswith(".")
    )


def test_compress_never_overwrites_an_existing_target(tmp_path):
    fixtures.build(tmp_path)
    target = tmp_path / "existing.sqlite.zst"
    target.write_bytes(b"do not replace")
    with pytest.raises(FileExistsError):
        artifact.compress(tmp_path / "fixture.sqlite", target)
    assert target.read_bytes() == b"do not replace"
    assert temporary_files(tmp_path) == []


def test_decompress_never_overwrites_an_existing_target(tmp_path):
    compressed, payload, _, _ = fixtures.build(tmp_path)
    target = tmp_path / "existing.sqlite"
    target.write_bytes(b"do not replace")
    with pytest.raises(FileExistsError):
        artifact.decompress(compressed, target, payload["artifact"])
    assert target.read_bytes() == b"do not replace"
    assert temporary_files(tmp_path) == []


def test_failed_decompression_leaves_no_target_and_no_spool(tmp_path):
    compressed, payload, _, _ = fixtures.build(tmp_path)
    metadata = dict(payload["artifact"], sqlite_sha256="0" * 64)
    target = tmp_path / "restored.sqlite"
    with pytest.raises(ContractError, match="digest"):
        artifact.decompress(compressed, target, metadata)
    assert not target.exists()
    assert temporary_files(tmp_path) == []


def test_successful_publish_replaces_the_spool_with_the_final_name(tmp_path):
    compressed, payload, _, _ = fixtures.build(tmp_path)
    target = tmp_path / "restored.sqlite"
    artifact.decompress(compressed, target, payload["artifact"])
    assert target.stat().st_size == payload["artifact"]["uncompressed_size_bytes"]
    assert temporary_files(tmp_path) == []
    rebuilt = tmp_path / "rebuilt.sqlite.zst"
    metadata = artifact.compress(target, rebuilt)
    assert metadata["sqlite_sha256"] == payload["artifact"]["sqlite_sha256"]
    assert rebuilt.exists() and temporary_files(tmp_path) == []
