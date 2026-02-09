from pathlib import Path


def _stub_aniworld_parser() -> None:
    import argparse
    import sys
    import types

    stub_parser = types.ModuleType("aniworld.parser")
    stub_parser.parse_arguments = lambda: argparse.Namespace()
    stub_parser.arguments = argparse.Namespace()
    sys.modules["aniworld.parser"] = stub_parser


def test_build_episode_accepts_season_zero_for_movies():
    import importlib

    _stub_aniworld_parser()
    build_episode = importlib.import_module("app.core.downloader.episode").build_episode

    episode = build_episode(
        slug="kaguya-sama-love-is-war",
        season=0,
        episode=1,
        site="aniworld.to",
    )

    assert episode.season == 0
    assert episode.episode == 1
    assert isinstance(episode.link, str)
    assert episode.link.endswith("/anime/stream/kaguya-sama-love-is-war/filme/film-1")


def test_download_episode_generates_s00e_hint(monkeypatch, tmp_path: Path):
    import importlib

    _stub_aniworld_parser()
    dl = importlib.import_module("app.core.downloader.download")

    captured: dict[str, str | None] = {"title_hint": None}

    class DummyEpisode:
        pass

    monkeypatch.setattr(
        dl,
        "build_episode",
        lambda **_kwargs: DummyEpisode(),
    )
    monkeypatch.setattr(
        dl,
        "get_direct_url_with_fallback",
        lambda _ep, preferred, language: ("https://example.test/master.m3u8", "VOE"),
    )

    def _fake_ydl_download(
        _url,
        dest_dir,
        *,
        title_hint,
        cookiefile,
        progress_cb,
        stop_event,
        force_no_proxy,
    ):
        del cookiefile, progress_cb, stop_event, force_no_proxy
        captured["title_hint"] = title_hint
        tmp_file = dest_dir / "tmp.mp4"
        tmp_file.write_bytes(b"ok")
        return tmp_file, {}

    monkeypatch.setattr(dl, "_ydl_download", _fake_ydl_download)
    monkeypatch.setattr(dl, "rename_to_release", lambda **kwargs: kwargs["path"])

    output = dl.download_episode(
        slug="kaguya-sama-love-is-war",
        season=0,
        episode=1,
        language="German Sub",
        dest_dir=tmp_path,
        site="aniworld.to",
    )

    assert output == tmp_path / "tmp.mp4"
    assert captured["title_hint"] is not None
    assert captured["title_hint"].startswith("kaguya-sama-love-is-war-S00E01-")
