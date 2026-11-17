"""The installed AniWorld transport must not replace Requests' dependency."""

import subprocess
import sys
import textwrap

import pytest


@pytest.mark.parametrize("imports", ["requests, niquests", "niquests, requests"])
def test_installed_http_transports_keep_separate_namespaces(imports: str) -> None:
    script = textwrap.dedent(
        f"""
        import {imports}
        from importlib.metadata import version
        import urllib3
        import urllib3_future

        assert urllib3.__version__ == version("urllib3"), "upstream namespace replaced"
        assert urllib3_future.__version__ == version("urllib3-future")
        assert requests.packages.urllib3 is urllib3
        assert niquests.packages.urllib3 is urllib3_future
        assert urllib3.HTTPConnectionPool is not urllib3_future.HTTPConnectionPool
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
