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


def test_build_episode_supports_aniworld_v4_api(monkeypatch):
    import importlib
    import sys
    import types
    from enum import Enum

    class Audio(Enum):
        GERMAN = "German"

    class Subtitles(Enum):
        NONE = "None"

    lang_tuple = (Audio.GERMAN, Subtitles.NONE)

    class FakeSession:
        def get(self, url: str, **_kwargs):
            return types.SimpleNamespace(url=f"{url}/resolved")

    class FakeAniworldEpisode:
        def __init__(self, *, url: str):
            self.url = url
            self.provider_data = types.SimpleNamespace(
                _data={lang_tuple: {"VOE": "https://aniworld.to/redirect/123"}}
            )

        def provider_link(self, language, provider):
            return self.provider_data._data[language][provider]

    fake_models = types.ModuleType("aniworld.models")
    fake_models.AniworldEpisode = FakeAniworldEpisode
    fake_models.SerienstreamEpisode = FakeAniworldEpisode

    fake_config = types.ModuleType("aniworld.config")
    fake_config.GLOBAL_SESSION = FakeSession()
    fake_config.LANG_KEY_MAP = {"1": lang_tuple}
    fake_config.LANG_LABELS = {"1": "German Dub"}
    fake_config.INVERSE_LANG_LABELS = {"German Dub": "1"}
    fake_config.INVERSE_LANG_KEY_MAP = {lang_tuple: "1"}

    fake_extractors = types.ModuleType("aniworld.extractors")
    fake_extractors.provider_functions = {
        "get_direct_link_from_voe": lambda url: f"{url}/master.m3u8"
    }

    monkeypatch.setitem(sys.modules, "aniworld.models", fake_models)
    monkeypatch.setitem(sys.modules, "aniworld.config", fake_config)
    monkeypatch.setitem(sys.modules, "aniworld.extractors", fake_extractors)

    original_episode_module = sys.modules.get("app.core.downloader.episode")
    sys.modules.pop("app.core.downloader.episode", None)
    episode_module = importlib.import_module("app.core.downloader.episode")
    if original_episode_module is not None:
        monkeypatch.setitem(
            sys.modules, "app.core.downloader.episode", original_episode_module
        )
    monkeypatch.setattr(
        episode_module.voe_extractor,
        "resolve_direct_link_from_redirect",
        lambda *, redirect_url, site: f"{redirect_url}/resolved/master.m3u8",
    )

    episode = episode_module.build_episode(
        slug="kaguya-sama-love-is-war",
        season=0,
        episode=1,
        site="aniworld.to",
    )

    assert episode.slug == "kaguya-sama-love-is-war"
    assert episode.season == 0
    assert episode.episode == 1
    assert episode.language_name == ["German Dub"]
    assert episode.link.endswith("/anime/stream/kaguya-sama-love-is-war/filme/film-1")
    assert (
        episode.get_direct_link("VOE", "German Dub")
        == "https://aniworld.to/redirect/123/resolved/master.m3u8"
    )


def test_build_episode_supports_sto_v4_api(monkeypatch):
    import importlib
    import sys
    import types
    from enum import Enum

    class Audio(Enum):
        GERMAN = "German"
        ENGLISH = "English"

    class Subtitles(Enum):
        NONE = "None"

    german_tuple = (Audio.GERMAN, Subtitles.NONE)
    english_tuple = (Audio.ENGLISH, Subtitles.NONE)

    class FakeSession:
        def get(self, url: str, **_kwargs):
            return types.SimpleNamespace(url=f"{url}/resolved")

    class FakeStoEpisode:
        def __init__(self, *, url: str):
            self.url = url
            self.provider_data = {
                german_tuple: {"VOE": "https://s.to/r/123"},
                english_tuple: {"VOE": "https://s.to/r/456"},
            }

        def _normalize_language(self, language):
            mapping = {
                "German Dub": german_tuple,
                "Deutsch": german_tuple,
                "English Dub": english_tuple,
                "Englisch": english_tuple,
            }
            return mapping[language]

        def provider_link(self, language, provider):
            return self.provider_data[language][provider]

    fake_models = types.ModuleType("aniworld.models")
    fake_models.AniworldEpisode = FakeStoEpisode
    fake_models.SerienstreamEpisode = FakeStoEpisode

    fake_config = types.ModuleType("aniworld.config")
    fake_config.GLOBAL_SESSION = FakeSession()

    fake_extractors = types.ModuleType("aniworld.extractors")
    fake_extractors.provider_functions = {
        "get_direct_link_from_voe": lambda url: f"{url}/master.m3u8"
    }

    monkeypatch.setitem(sys.modules, "aniworld.models", fake_models)
    monkeypatch.setitem(sys.modules, "aniworld.config", fake_config)
    monkeypatch.setitem(sys.modules, "aniworld.extractors", fake_extractors)

    original_episode_module = sys.modules.get("app.core.downloader.episode")
    sys.modules.pop("app.core.downloader.episode", None)
    episode_module = importlib.import_module("app.core.downloader.episode")
    if original_episode_module is not None:
        monkeypatch.setitem(
            sys.modules, "app.core.downloader.episode", original_episode_module
        )
    monkeypatch.setattr(
        episode_module.voe_extractor,
        "resolve_direct_link_from_redirect",
        lambda *, redirect_url, site: f"{redirect_url}/resolved/master.m3u8",
    )

    episode = episode_module.build_episode(
        slug="9-1-1",
        season=1,
        episode=5,
        site="s.to",
    )

    assert episode.slug == "9-1-1"
    assert episode.season == 1
    assert episode.episode == 5
    assert episode.language_name == ["German Dub", "English Dub"]
    assert episode.link.endswith("/serie/9-1-1/staffel-1/episode-5")
    assert (
        episode.get_direct_link("VOE", "German Dub")
        == "https://s.to/r/123/resolved/master.m3u8"
    )


def test_sto_v4_missing_provider_does_not_mask_available_language(monkeypatch):
    import importlib
    import sys
    import types
    from enum import Enum

    class Audio(Enum):
        GERMAN = "German"
        ENGLISH = "English"

    class Subtitles(Enum):
        NONE = "None"

    german_tuple = (Audio.GERMAN, Subtitles.NONE)
    english_tuple = (Audio.ENGLISH, Subtitles.NONE)

    class FakeSession:
        def get(self, url: str, **_kwargs):
            return types.SimpleNamespace(url=f"{url}/resolved")

    class FakeStoEpisode:
        def __init__(self, *, url: str):
            self.url = url
            self.provider_data = {
                german_tuple: {
                    "VOE": "https://s.to/r/voe",
                    "Streamtape": "https://s.to/r/streamtape",
                },
                english_tuple: {"VOE": "https://s.to/r/eng-voe"},
            }

        def _normalize_language(self, language):
            mapping = {
                "German Dub": german_tuple,
                "English Dub": english_tuple,
            }
            return mapping[language]

        def provider_link(self, language, provider):
            provider_dict = self.provider_data.get(language)
            if not provider_dict:
                raise ValueError(f"No provider data found for language: {language}")
            url = provider_dict.get(provider)
            if not url:
                raise ValueError(
                    f"Provider '{provider}' not found for language: {language}."
                )
            return url

    fake_models = types.ModuleType("aniworld.models")
    fake_models.AniworldEpisode = FakeStoEpisode
    fake_models.SerienstreamEpisode = FakeStoEpisode

    fake_config = types.ModuleType("aniworld.config")
    fake_config.GLOBAL_SESSION = FakeSession()

    fake_extractors = types.ModuleType("aniworld.extractors")
    fake_extractors.provider_functions = {
        "get_direct_link_from_voe": lambda url: f"{url}/master.m3u8",
        "get_direct_link_from_streamtape": lambda url: f"{url}/master.m3u8",
    }

    monkeypatch.setitem(sys.modules, "aniworld.models", fake_models)
    monkeypatch.setitem(sys.modules, "aniworld.config", fake_config)
    monkeypatch.setitem(sys.modules, "aniworld.extractors", fake_extractors)

    original_episode_module = sys.modules.get("app.core.downloader.episode")
    sys.modules.pop("app.core.downloader.episode", None)
    episode_module = importlib.import_module("app.core.downloader.episode")
    if original_episode_module is not None:
        monkeypatch.setitem(
            sys.modules, "app.core.downloader.episode", original_episode_module
        )
    monkeypatch.setattr(
        episode_module.voe_extractor,
        "resolve_direct_link_from_redirect",
        lambda *, redirect_url, site: f"{redirect_url}/resolved/master.m3u8",
    )

    original_provider_resolution = sys.modules.get(
        "app.core.downloader.provider_resolution"
    )
    sys.modules.pop("app.core.downloader.provider_resolution", None)
    provider_resolution = importlib.import_module(
        "app.core.downloader.provider_resolution"
    )
    if original_provider_resolution is not None:
        monkeypatch.setitem(
            sys.modules,
            "app.core.downloader.provider_resolution",
            original_provider_resolution,
        )

    episode = episode_module.build_episode(
        slug="better-call-saul",
        season=1,
        episode=1,
        site="s.to",
    )

    direct_url, provider = provider_resolution.get_direct_url_with_fallback(
        episode,
        preferred="Filemoon",
        language="German Dub",
    )

    assert provider == "VOE"
    assert direct_url == "https://s.to/r/voe/resolved/master.m3u8"


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
    ):
        """
        Test helper that simulates a youtube-dl download by writing a temporary mp4 and recording the provided title hint.

        Parameters:
            _url: URL to download (ignored).
            dest_dir (Path): Directory where the temporary file will be created.
            title_hint (str): Title hint to record into the test `captured` mapping.
            cookiefile, progress_cb, stop_event: Ignored keyword-only arguments present to match the real downloader signature.

        Returns:
            tuple: (Path to the created "tmp.mp4" file in `dest_dir`, info_dict) where `info_dict` is an empty dict.
        """
        del cookiefile, progress_cb, stop_event
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
    ):
        """
        Create a temporary MP4 file named "tmp.mp4" inside dest_dir and return its path along with an empty info dictionary.

        Parameters:
            dest_dir (pathlib.Path): Directory where the temporary "tmp.mp4" file will be written.

        Returns:
            (pathlib.Path, dict): Tuple containing the Path to the written "tmp.mp4" and an empty dictionary.
        """
        del title_hint, cookiefile, progress_cb, stop_event
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
    ):
        del title_hint, cookiefile, progress_cb, stop_event
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
