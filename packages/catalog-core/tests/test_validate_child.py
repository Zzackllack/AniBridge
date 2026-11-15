"""The bounded validator CLI keeps its argument and input contracts typed."""

import json
import subprocess
import sys

import pytest

from catalog_core import fixtures

# limit_child sets Linux resource limits; macOS rejects RLIMIT_AS outright, so
# these CLI contract tests run the real main() with only that syscall stubbed.
BOOTSTRAP = """
import sys
import catalog_core.validate_child as child
child.limit_child = lambda **kwargs: None
sys.argv = ["validate_child", *sys.argv[1:]]
child.main()
"""


def run(*arguments):
    return subprocess.run(
        [sys.executable, "-c", BOOTSTRAP, *arguments],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def payload_file(tmp_path, payload):
    path = tmp_path / "payload.json"
    path.write_text(json.dumps(payload))
    return path


def test_validate_and_saved_run_without_a_destination(tmp_path):
    _, payload, _, _ = fixtures.build(tmp_path)
    assert (
        run(
            "validate",
            str(tmp_path / "fixture.sqlite"),
            str(payload_file(tmp_path, payload)),
        ).returncode
        == 0
    )
    assert (
        run(
            "saved", str(tmp_path / "fixture.sqlite"), str(tmp_path / "payload.json")
        ).returncode
        == 0
    )


def test_decompress_requires_a_destination(tmp_path):
    compressed, payload, _, _ = fixtures.build(tmp_path)
    result = run("decompress", str(compressed), str(payload_file(tmp_path, payload)))
    assert result.returncode == 2 and "--destination is required" in result.stderr


def test_destination_only_applies_to_decompress(tmp_path):
    _, payload, _, _ = fixtures.build(tmp_path)
    result = run(
        "validate",
        str(tmp_path / "fixture.sqlite"),
        str(payload_file(tmp_path, payload)),
        "--destination",
        str(tmp_path / "unused.sqlite"),
    )
    assert result.returncode == 2 and "only applies to decompress" in result.stderr


def test_oversized_payload_is_rejected_before_it_is_loaded(tmp_path):
    fixtures.build(tmp_path)
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b'"' + b"x" * 65536 + b'"')
    result = run("validate", str(tmp_path / "fixture.sqlite"), str(oversized))
    assert result.returncode == 1 and "JSON too large" in result.stderr


def test_payload_read_asks_for_one_byte_past_the_cap():
    from catalog_core import validate_child
    from catalog_core.json_codec import ContractError

    class Stream:
        def __init__(self):
            self.sizes = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size=-1):
            self.sizes.append(size)
            if size < 0:
                raise AssertionError("unbounded payload read")
            return b'"' + b"x" * size

    class Path:
        def __init__(self):
            self.stream = Stream()

        def open(self, mode):
            assert mode == "rb"
            return self.stream

    path = Path()
    with pytest.raises(ContractError, match="JSON too large"):
        validate_child._read_payload(path)
    assert path.stream.sizes == [validate_child.PAYLOAD_CAP + 1]


def test_decompress_publishes_exactly_once(tmp_path):
    compressed, payload, _, _ = fixtures.build(tmp_path)
    meta = payload_file(tmp_path, payload)
    target = tmp_path / "restored.sqlite"
    assert (
        run(
            "decompress", str(compressed), str(meta), "--destination", str(target)
        ).returncode
        == 0
    )
    assert target.stat().st_size == payload["artifact"]["uncompressed_size_bytes"]
    before = target.read_bytes()
    second = run("decompress", str(compressed), str(meta), "--destination", str(target))
    assert second.returncode == 1 and target.read_bytes() == before
