"""Check generated I/O with real resolver/transfer; not client import proof."""

import importlib.util
import os
from pathlib import Path

import httpx
import pytest

from app.core.downloader import provider_policy
from app.catalog import media_transport
from app.catalog.resolution_transport import Budget


@pytest.mark.parametrize("provider", ["aniworld.to", "s.to"])
def test_fixture_streams_through_resolver_and_transfer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    original_client = httpx.Client
    original_validate = provider_policy._validate_request_url
    home = os.environ.get("HOME")
    monkeypatch.setenv("CATALOG_SITES", provider)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ANIWORLD_INSTALL_FOLDER", str(tmp_path / "upstream"))
    filename = Path(__file__).parent / "hooks" / "sitecustomize.py"
    spec = importlib.util.spec_from_file_location("acceptance_inputs", filename)
    fixture = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(fixture)
        fixture.MEDIA = tmp_path / "generated.mp4"
        body = b"generated streaming boundary bytes" * 10000
        fixture.MEDIA.write_bytes(body)
        events = []
        fixture.event = events.append
        monkeypatch.setattr(media_transport, "_validate_request_url", fixture.validate)
        from app.catalog.aniworld_resolution import resolve
        from app.catalog.media_download import transfer

        budget = Budget(client=fixture.Client(), validate_url=fixture.validate)
        try:
            media = resolve(
                {
                    "provider": provider,
                    "path": fixture.EPISODE,
                    "language": "en-dub" if provider == "s.to" else "en-sub",
                },
                "https://fixture.invalid",
                ("Vidoza",),
                budget,
            )
        finally:
            budget.close()
        assert media.host == "Vidoza"
        tracks = transfer(media.url, tmp_path / "tracks", lambda update: None)
        assert len(tracks) == 1 and tracks[0].read_bytes() == body
        assert set(events) == {"provider", "player", "media"}
        with pytest.raises(ValueError, match="outside the single"):
            fixture.validate("https://fixture.invalid/unlisted")
        assert os.environ.get("HOME") == home
    finally:
        httpx.Client = original_client
        provider_policy._validate_request_url = original_validate
