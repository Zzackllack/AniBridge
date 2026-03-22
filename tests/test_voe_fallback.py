def test_choose_redirect_candidate_prefers_embed_target():
    from app.core.downloader.episode import _choose_redirect_candidate

    html = """
    <html>
      <head>
        <script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script>
        <link href="https://fonts.gstatic.com/example.woff2" rel="preload">
      </head>
      <body>
        <script>
          window.location.href = 'https://mirror.example/e/abc123';
        </script>
      </body>
    </html>
    """

    assert (
        _choose_redirect_candidate(html, "https://voe.sx/e/original")
        == "https://mirror.example/e/abc123"
    )


def test_sto_voe_fallback_follows_nested_redirects(monkeypatch):
    import importlib
    import sys
    import types
    from enum import Enum

    class Audio(Enum):
        GERMAN = "German"

    class Subtitles(Enum):
        NONE = "None"

    german_tuple = (Audio.GERMAN, Subtitles.NONE)
    raw_redirect = "https://s.to/r/voe-token"
    embed_url = "https://voe.sx/e/abc123"
    nested_embed_url = "https://dianaavoidthey.com/e/abc123"
    final_source = "https://cdn.example/master.m3u8"

    class FakeResponse:
        def __init__(self, *, url: str, text: str = ""):
            self.url = url
            self.text = text
            self.status_code = 200

        def raise_for_status(self):
            return None

    class FakeSession:
        def get(self, url: str, **_kwargs):
            if url == raw_redirect:
                return FakeResponse(url=embed_url)
            if url == embed_url:
                return FakeResponse(
                    url=embed_url,
                    text=(
                        f"<script>window.location.href='{nested_embed_url}'</script>"
                    ),
                )
            if url == nested_embed_url:
                return FakeResponse(
                    url=nested_embed_url, text="<html>final-html</html>"
                )
            raise AssertionError(f"Unexpected URL fetched: {url}")

    class FakeStoEpisode:
        def __init__(self, *, url: str):
            self.url = url
            self.provider_data = {german_tuple: {"VOE": raw_redirect}}

        def _normalize_language(self, language):
            return {"German Dub": german_tuple}[language]

    fake_models = types.ModuleType("aniworld.models")
    fake_models.AniworldEpisode = FakeStoEpisode
    fake_models.SerienstreamEpisode = FakeStoEpisode

    fake_config = types.ModuleType("aniworld.config")
    fake_config.GLOBAL_SESSION = FakeSession()
    fake_config.DEFAULT_USER_AGENT = "test-agent"
    fake_config.PROVIDER_HEADERS_D = {"VOE": {"User-Agent": "test-agent"}}

    fake_extractors = types.ModuleType("aniworld.extractors")

    def _broken_voe_extractor(_url: str):
        raise ValueError("No VOE video source found in page.")

    fake_extractors.provider_functions = {
        "get_direct_link_from_voe": _broken_voe_extractor
    }

    fake_voe = types.ModuleType("aniworld.extractors.provider.voe")

    def _extract_voe_source_from_html(html: str):
        return final_source if html == "<html>final-html</html>" else None

    fake_voe.extract_voe_source_from_html = _extract_voe_source_from_html

    monkeypatch.setitem(sys.modules, "aniworld.models", fake_models)
    monkeypatch.setitem(sys.modules, "aniworld.config", fake_config)
    monkeypatch.setitem(sys.modules, "aniworld.extractors", fake_extractors)
    monkeypatch.setitem(sys.modules, "aniworld.extractors.provider.voe", fake_voe)

    original_episode_module = sys.modules.get("app.core.downloader.episode")
    sys.modules.pop("app.core.downloader.episode", None)
    episode_module = importlib.import_module("app.core.downloader.episode")
    if original_episode_module is not None:
        monkeypatch.setitem(
            sys.modules, "app.core.downloader.episode", original_episode_module
        )

    episode = episode_module.build_episode(
        slug="better-call-saul",
        season=1,
        episode=1,
        site="s.to",
    )

    assert episode.get_direct_link("VOE", "German Dub") == final_source
