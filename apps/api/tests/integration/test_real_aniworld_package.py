from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap


def test_real_installed_aniworld_contracts(tmp_path: Path) -> None:
    """Probe the installed upstream package in a clean subprocess."""
    install_dir = tmp_path / "upstream-config"
    data_dir = tmp_path / "data"
    env = os.environ.copy()
    env.update(
        {
            "ANIWORLD_INSTALL_FOLDER": str(install_dir),
            "DATA_DIR": str(data_dir),
            "DOWNLOAD_DIR": str(tmp_path / "downloads"),
            "STO_BASE_URL": "https://configured.example",
            "ANIBRIDGE_UPDATE_CHECK": "0",
            "PUBLIC_IP_CHECK_ENABLED": "0",
        }
    )
    script = textwrap.dedent(
        """
        import inspect
        import os
        from importlib.metadata import version
        from pathlib import Path

        from app.utils.aniworld_compat import prepare_aniworld_home

        original_home = os.environ.get("HOME")
        install_dir = prepare_aniworld_home()
        import aniworld.config as config
        import aniworld.extractors as extractors
        import aniworld.models as models
        from aniworld.extractors.provider.voe import extract_voe_source_from_html
        from app.core.downloader.episode import build_episode

        assert version("aniworld") == "5.0.6"
        assert not hasattr(models, "Episode")
        models.AniworldEpisode(
            url="https://aniworld.to/anime/stream/example/staffel-1/episode-1"
        )
        models.SerienstreamEpisode(
            url="https://serienstream.to/serie/example/staffel-1/episode-1"
        )
        assert Path(config.ANIWORLD_CONFIG_DIR) == install_dir
        assert os.environ.get("HOME") == original_home

        episode = build_episode(
            site="aniworld.to", slug="example", season=0, episode=1
        )
        assert episode.link.endswith("/filme/film-1")
        serienstream = build_episode(
            site="s.to", slug="example", season=1, episode=2
        )
        assert serienstream.link.startswith("https://configured.example/")
        assert type(serienstream._backend).__name__ == "SerienstreamSource"

        hosts = (
            "voe", "filemoon", "streamtape", "vidmoly",
            "doodstream", "loadx", "luluvdo", "vidoza",
        )
        for host in hosts:
            function = extractors.provider_functions[
                f"get_direct_link_from_{host}"
            ]
            assert callable(function)
            assert len(inspect.signature(function).parameters) >= 1

        html = "<script>var sources = {'hls': 'https://cdn.example/master.m3u8'};</script>"
        assert extract_voe_source_from_html(html) == "https://cdn.example/master.m3u8"
        print("REAL_PACKAGE_CONTRACT_OK")
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "REAL_PACKAGE_CONTRACT_OK" in result.stdout
