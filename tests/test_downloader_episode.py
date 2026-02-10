from pathlib import Path


def test_build_episode_accepts_season_zero_for_movies(stub_aniworld_parser):
    import importlib

    del stub_aniworld_parser
    build_episode = importlib.import_module("app.core.downloader.episode").build_episode

    episode = build_episode(
        slug="kaguya-sama-love-is-war",
        season=0,
        episode=1,
        site="aniworld.to",
    )

    assert episode.season == 0
    assert episode.episode == 1
    assert episode.slug == "kaguya-sama-love-is-war"
    assert isinstance(episode.link, str)
    assert episode.link.endswith("/anime/stream/kaguya-sama-love-is-war/filme/film-1")


def test_download_episode_generates_s00e_hint(
    stub_aniworld_parser, monkeypatch, tmp_path: Path
):
    import importlib

    del stub_aniworld_parser
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
        """
        Test helper that simulates a youtube-dl download by writing a temporary mp4 and recording the provided title hint.

        Parameters:
            _url: URL to download (ignored).
            dest_dir (Path): Directory where the temporary file will be created.
            title_hint (str): Title hint to record into the test `captured` mapping.
            cookiefile, progress_cb, stop_event, force_no_proxy: Ignored keyword-only arguments present to match the real downloader signature.

        Returns:
            tuple: (Path to the created "tmp.mp4" file in `dest_dir`, info_dict) where `info_dict` is an empty dict.
        """
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


def test_download_episode_uses_title_hint_as_release_override(
    stub_aniworld_parser, monkeypatch, tmp_path: Path
):
    import importlib

    del stub_aniworld_parser
    dl = importlib.import_module("app.core.downloader.download")

    captured: dict[str, str | None] = {"release_name_override": None}

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
        """
        Create a temporary MP4 file named "tmp.mp4" inside dest_dir and return its path along with an empty info dictionary.

        Parameters:
            dest_dir (pathlib.Path): Directory where the temporary "tmp.mp4" file will be written.

        Returns:
            (pathlib.Path, dict): Tuple containing the Path to the written "tmp.mp4" and an empty dictionary.
        """
        del title_hint, cookiefile, progress_cb, stop_event, force_no_proxy
        tmp_file = dest_dir / "tmp.mp4"
        tmp_file.write_bytes(b"ok")
        return tmp_file, {}

    def _fake_rename_to_release(**kwargs):
        """
        Capture the 'release_name_override' value from keyword arguments and return the supplied path.

        Parameters:
            kwargs (dict): Keyword arguments expected to include:
                - path (str): filesystem path to return.
                - release_name_override (str, optional): release name override to capture.

        Returns:
            str: The `path` value from `kwargs`.
        """
        captured["release_name_override"] = kwargs.get("release_name_override")
        return kwargs["path"]

    monkeypatch.setattr(dl, "_ydl_download", _fake_ydl_download)
    monkeypatch.setattr(dl, "rename_to_release", _fake_rename_to_release)

    output = dl.download_episode(
        slug="kaguya-sama-love-is-war",
        season=0,
        episode=4,
        language="German Dub",
        dest_dir=tmp_path,
        site="aniworld.to",
        title_hint="Kaguya.sama.Love.is.War.S00E05.1080p.WEB.H264.GER-ANIWORLD",
    )

    assert output == tmp_path / "tmp.mp4"
    assert (
        captured["release_name_override"]
        == "Kaguya.sama.Love.is.War.S00E05.1080p.WEB.H264.GER-ANIWORLD"
    )


def test_download_episode_sets_release_override_to_none_when_hint_is_empty(
    stub_aniworld_parser, monkeypatch, tmp_path: Path
):
    import importlib

    del stub_aniworld_parser
    dl = importlib.import_module("app.core.downloader.download")

    captured: dict[str, str | None] = {"release_name_override": "sentinel"}

    class DummyEpisode:
        pass

    monkeypatch.setattr(dl, "build_episode", lambda **_kwargs: DummyEpisode())
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
        del title_hint, cookiefile, progress_cb, stop_event, force_no_proxy
        tmp_file = dest_dir / "tmp.mp4"
        tmp_file.write_bytes(b"ok")
        return tmp_file, {}

    def _fake_rename_to_release(**kwargs):
        captured["release_name_override"] = kwargs.get("release_name_override")
        return kwargs["path"]

    monkeypatch.setattr(dl, "_ydl_download", _fake_ydl_download)
    monkeypatch.setattr(dl, "rename_to_release", _fake_rename_to_release)

    output = dl.download_episode(
        slug="kaguya-sama-love-is-war",
        season=0,
        episode=4,
        language="German Dub",
        dest_dir=tmp_path,
        site="aniworld.to",
        title_hint=" [STRM] ",
    )

    assert output == tmp_path / "tmp.mp4"
    assert captured["release_name_override"] is None
