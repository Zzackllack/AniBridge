import pytest
import requests


def test_choose_redirect_candidate_prefers_embed_target(monkeypatch):
    from app.core.downloader.extractors import voe as voe_module

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

    monkeypatch.setattr(voe_module, "host_is_public", lambda _host: True)

    assert (
        voe_module.choose_redirect_candidate(html, "https://voe.sx/e/original")
        == "https://mirror.example/e/abc123"
    )


def test_sto_voe_redirect_resolver_follows_nested_redirects(monkeypatch):
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
            """
            No-op replacement for Response.raise_for_status that never raises an exception.

            This method intentionally does not raise for any HTTP status and can be used on fake response objects to bypass HTTP error checking in tests.
            """
            return None

    class FakeStoEpisode:
        def __init__(self, *, url: str):
            """
            Initialize a fake episode object with a VOE provider redirect entry.

            Sets the instance's `url` attribute to the given `url` and populates `provider_data`
            with a mapping from `german_tuple` to a dict containing the `"VOE"` redirect token.

            Parameters:
                url (str): The episode URL to store on the instance.
            """
            self.url = url
            self.provider_data = {german_tuple: {"VOE": raw_redirect}}

        def _normalize_language(self, language):
            return {"German Dub": german_tuple}[language]

    fake_models = types.ModuleType("aniworld.models")
    fake_models.AniworldEpisode = FakeStoEpisode
    fake_models.SerienstreamEpisode = FakeStoEpisode

    fake_config = types.ModuleType("aniworld.config")
    fake_config.DEFAULT_USER_AGENT = "test-agent"
    fake_config.GLOBAL_SESSION = types.SimpleNamespace(
        get=lambda url, **_kwargs: (_ for _ in ()).throw(
            AssertionError(f"Unexpected fallback redirect fetch: {url}")
        )
    )
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
    monkeypatch.setattr(
        episode_module.voe_extractor.requests,
        "get",
        lambda url, **_kwargs: (
            FakeResponse(
                url=embed_url,
                text=f"<script>window.location.href='{nested_embed_url}'</script>",
            )
            if url == raw_redirect
            else (
                FakeResponse(url=nested_embed_url, text="<html>final-html</html>")
                if url == nested_embed_url
                else (_ for _ in ()).throw(
                    AssertionError(f"Unexpected URL fetched: {url}")
                )
            )
        ),
    )

    episode = episode_module.build_episode(
        slug="better-call-saul",
        season=1,
        episode=1,
        site="s.to",
    )

    assert episode.get_direct_link("VOE", "German Dub") == final_source


def test_voe_direct_link_fallback_follows_nested_redirects(monkeypatch):
    import importlib
    import sys
    import types

    provider_url = "https://voe.sx/e/abc123"
    nested_embed_url = "https://dianaavoidthey.com/e/abc123"
    final_source = "https://cdn.example/master.m3u8"

    class FakeResponse:
        def __init__(self, *, url: str, text: str):
            """
            Initialize the fake HTTP response with its final URL and body text.

            Parameters:
                url (str): The response's final URL (after redirects).
                text (str): The response body content, typically HTML.
            """
            self.url = url
            self.text = text

        def raise_for_status(self):
            """
            No-op replacement for Response.raise_for_status that never raises an exception.

            This method intentionally does not raise for any HTTP status and can be used on fake response objects to bypass HTTP error checking in tests.
            """
            return None

    class FakeSession:
        def __init__(self):
            """
            Initialize the fake session and create a list to record requested (url, timeout) pairs.

            The `calls` attribute is an empty list that will be appended with tuples `(url, timeout)` each time `get` is invoked.
            """
            self.calls: list[tuple[str, int]] = []

        def get(self, url: str, **kwargs):
            """
            Simulated session GET that records the timeout and returns canned FakeResponse objects for two specific test URLs.

            Parameters:
                url (str): URL requested.
                **kwargs: Arbitrary keyword arguments; expects a `timeout` key which is recorded.

            Returns:
                FakeResponse: For `provider_url`, a response whose text contains a script redirecting to `nested_embed_url`; for `nested_embed_url`, a response with text `"<html>final-html</html>"`.

            Raises:
                AssertionError: If an unexpected URL is requested.
            """
            self.calls.append((url, kwargs["timeout"]))
            if url == provider_url:
                return FakeResponse(
                    url=provider_url,
                    text=f"<script>window.location.href='{nested_embed_url}'</script>",
                )
            if url == nested_embed_url:
                return FakeResponse(
                    url=nested_embed_url, text="<html>final-html</html>"
                )
            raise AssertionError(f"Unexpected URL fetched: {url}")

    fake_config = types.ModuleType("aniworld.config")
    fake_config.DEFAULT_USER_AGENT = "test-agent"
    fake_config.GLOBAL_SESSION = FakeSession()
    fake_config.PROVIDER_HEADERS_D = {"VOE": {"User-Agent": "test-agent"}}

    fake_voe = types.ModuleType("aniworld.extractors.provider.voe")
    fake_voe.extract_voe_source_from_html = lambda html: (
        final_source if html == "<html>final-html</html>" else None
    )

    monkeypatch.setitem(sys.modules, "aniworld.config", fake_config)
    monkeypatch.setitem(sys.modules, "aniworld.extractors.provider.voe", fake_voe)

    voe_module = importlib.import_module("app.core.downloader.extractors.voe")
    monkeypatch.setattr(voe_module, "PROVIDER_REDIRECT_TIMEOUT_SECONDS", 7)

    assert (
        voe_module.resolve_direct_link_fallback(initial_urls=[provider_url])
        == final_source
    )
    assert fake_config.GLOBAL_SESSION.calls == [
        (provider_url, 7),
        (nested_embed_url, 7),
    ]


def test_resolve_provider_redirect_url_retries_on_timeout(monkeypatch):
    import importlib
    import sys
    import types

    attempts = {"count": 0}

    class FakeResponse:
        url = "https://voe.sx/e/recovered"

    class FakeSession:
        def get(self, url: str, **kwargs):
            attempts["count"] += 1
            assert url == "https://s.to/r/token"
            assert kwargs["timeout"] == 3
            if attempts["count"] < 3:
                raise TimeoutError("timed out")
            return FakeResponse()

    fake_config = types.ModuleType("aniworld.config")
    fake_config.GLOBAL_SESSION = FakeSession()

    monkeypatch.setitem(sys.modules, "aniworld.config", fake_config)

    episode_module = importlib.import_module("app.core.downloader.episode")
    monkeypatch.setattr(episode_module, "PROVIDER_REDIRECT_TIMEOUT_SECONDS", 3)
    monkeypatch.setattr(episode_module, "PROVIDER_REDIRECT_RETRIES", 2)

    assert (
        episode_module._resolve_provider_redirect_url("https://s.to/r/token", "VOE")
        == "https://voe.sx/e/recovered"
    )
    assert attempts["count"] == 3


def test_voe_direct_link_retries_on_transient_fetch_abort(monkeypatch):
    import importlib
    import sys
    import types
    from enum import Enum

    class Audio(Enum):
        GERMAN = "German"

    class Subtitles(Enum):
        NONE = "None"

    german_tuple = (Audio.GERMAN, Subtitles.NONE)
    redirect_url = "https://s.to/r/voe-token"
    request_attempts = {"count": 0}

    class FakeResponse:
        def __init__(self, url: str, text: str = "<html>ok</html>"):
            """
            Initialize a fake HTTP response used in tests.

            Parameters:
                url (str): The response URL.
                text (str): The response body text; defaults to "<html>ok</html>".

            Notes:
                The instance will have a `status_code` attribute set to 200.
            """
            self.url = url
            self.text = text
            self.status_code = 200

        def raise_for_status(self):
            """
            No-op replacement for Response.raise_for_status that never raises an exception.

            This method intentionally does not raise for any HTTP status and can be used on fake response objects to bypass HTTP error checking in tests.
            """
            return None

    def _fake_requests_get(url: str, **_kwargs):
        """
        Simulates a requests.get call that fails once with a transient connection error then returns a recovered FakeResponse.

        Parameters:
            url (str): Expected request URL; the function asserts it equals the test's `redirect_url`.
            **_kwargs: Ignored keyword arguments forwarded by callers.

        Returns:
            FakeResponse: A response whose `.url` is "https://dianaavoidthey.com/e/recovered" after the first failed attempt.

        Raises:
            requests.ConnectionError: Raised on the first invocation to simulate a transient network failure.

        Side effects:
            Increments `request_attempts["count"]` on each call.
        """
        request_attempts["count"] += 1
        assert url == redirect_url
        if request_attempts["count"] == 1:
            raise requests.ConnectionError(
                "('Connection aborted.', OSError(5, 'Input/output error'))"
            )
        return FakeResponse(url="https://dianaavoidthey.com/e/recovered")

    class FakeStoEpisode:
        def __init__(self, *, url: str):
            """
            Initialize the fake episode with the given URL and a preset VOE provider mapping for the German Dub language.

            Parameters:
                url (str): The episode URL to store on the instance (assigned to `self.url`).

            Attributes set:
                provider_data (dict): A mapping from `german_tuple` to `{"VOE": redirect_url}` used by tests to simulate provider data.
            """
            self.url = url
            self.provider_data = {german_tuple: {"VOE": redirect_url}}

        def _normalize_language(self, language):
            """
            Map a human-readable language label to the episode's normalized language tuple.

            Parameters:
                language (str): Human-readable language label (for example, "German Dub").

            Returns:
                tuple: The internal language tuple corresponding to the provided label.
            """
            return {"German Dub": german_tuple}[language]

    fake_models = types.ModuleType("aniworld.models")
    fake_models.AniworldEpisode = FakeStoEpisode
    fake_models.SerienstreamEpisode = FakeStoEpisode

    fake_config = types.ModuleType("aniworld.config")
    fake_config.DEFAULT_USER_AGENT = "test-agent"
    fake_config.GLOBAL_SESSION = types.SimpleNamespace(
        get=lambda url, **_kwargs: (_ for _ in ()).throw(
            AssertionError(f"Unexpected fallback redirect fetch: {url}")
        )
    )
    fake_config.PROVIDER_HEADERS_D = {"VOE": {"User-Agent": "test-agent"}}
    fake_extractors = types.ModuleType("aniworld.extractors")
    fake_voe = types.ModuleType("aniworld.extractors.provider.voe")

    fake_extractors.provider_functions = {"get_direct_link_from_voe": lambda _url: None}
    fake_voe.extract_voe_source_from_html = lambda html: (
        "https://voe.sx/e/second-attempt/master.m3u8"
        if html == "<html>ok</html>"
        else None
    )
    monkeypatch.setitem(sys.modules, "aniworld.models", fake_models)
    monkeypatch.setitem(sys.modules, "aniworld.config", fake_config)
    monkeypatch.setitem(sys.modules, "aniworld.extractors", fake_extractors)
    monkeypatch.setitem(sys.modules, "aniworld.extractors.provider.voe", fake_voe)

    episode_module = importlib.import_module("app.core.downloader.episode")
    monkeypatch.setattr(episode_module, "PROVIDER_REDIRECT_RETRIES", 2)
    monkeypatch.setattr(episode_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        episode_module.voe_extractor.requests, "get", _fake_requests_get
    )

    episode = episode_module.build_episode(
        slug="better-call-saul",
        season=2,
        episode=1,
        site="s.to",
    )

    assert (
        episode.get_direct_link("VOE", "German Dub")
        == "https://voe.sx/e/second-attempt/master.m3u8"
    )
    assert request_attempts["count"] == 2


def test_voe_direct_link_reports_turnstile_requirement(monkeypatch):
    import importlib
    import sys
    import types
    from enum import Enum

    class Audio(Enum):
        GERMAN = "German"

    class Subtitles(Enum):
        NONE = "None"

    german_tuple = (Audio.GERMAN, Subtitles.NONE)
    redirect_url = "https://serienstream.to/r?token=abc"

    class FakeResponse:
        def __init__(self, text: str):
            """
            Initialize a test response object with the given HTML body.

            Parameters:
                text (str): The HTML response body to expose via the `text` attribute.

            Attributes created:
                url (str): Preexisting redirect URL captured from the surrounding test scope.
                text (str): The provided HTML body.
                status_code (int): HTTP status code, set to 200.
            """
            self.url = redirect_url
            self.text = text
            self.status_code = 200

        def raise_for_status(self):
            """
            No-op replacement for Response.raise_for_status that never raises an exception.

            This method intentionally does not raise for any HTTP status and can be used on fake response objects to bypass HTTP error checking in tests.
            """
            return None

    class FakeStoEpisode:
        def __init__(self, *, url: str):
            """
            Initialize the fake episode with the given URL and a preset VOE provider mapping for the German Dub language.

            Parameters:
                url (str): The episode URL to store on the instance (assigned to `self.url`).

            Attributes set:
                provider_data (dict): A mapping from `german_tuple` to `{"VOE": redirect_url}` used by tests to simulate provider data.
            """
            self.url = url
            self.provider_data = {german_tuple: {"VOE": redirect_url}}

        def _normalize_language(self, language):
            """
            Map a human-readable language label to the episode's normalized language tuple.

            Parameters:
                language (str): Human-readable language label (for example, "German Dub").

            Returns:
                tuple: The internal language tuple corresponding to the provided label.
            """
            return {"German Dub": german_tuple}[language]

    fake_models = types.ModuleType("aniworld.models")
    fake_models.AniworldEpisode = FakeStoEpisode
    fake_models.SerienstreamEpisode = FakeStoEpisode

    fake_config = types.ModuleType("aniworld.config")
    fake_config.DEFAULT_USER_AGENT = "test-agent"
    fake_config.GLOBAL_SESSION = types.SimpleNamespace(
        get=lambda url, **_kwargs: types.SimpleNamespace(
            url=url,
            text="",
            raise_for_status=lambda: None,
        )
    )
    fake_config.PROVIDER_HEADERS_D = {"VOE": {"User-Agent": "test-agent"}}

    fake_extractors = types.ModuleType("aniworld.extractors")
    fake_extractors.provider_functions = {"get_direct_link_from_voe": lambda _url: None}
    fake_voe = types.ModuleType("aniworld.extractors.provider.voe")
    fake_voe.extract_voe_source_from_html = lambda _html: None

    monkeypatch.setitem(sys.modules, "aniworld.models", fake_models)
    monkeypatch.setitem(sys.modules, "aniworld.config", fake_config)
    monkeypatch.setitem(sys.modules, "aniworld.extractors", fake_extractors)
    monkeypatch.setitem(sys.modules, "aniworld.extractors.provider.voe", fake_voe)

    episode_module = importlib.import_module("app.core.downloader.episode")
    sleep_calls: list[int] = []
    monkeypatch.setattr(
        episode_module.voe_extractor,
        "PROVIDER_REDIRECT_RETRIES",
        2,
    )
    monkeypatch.setattr(
        episode_module.voe_extractor,
        "PROVIDER_CHALLENGE_BACKOFF_SECONDS",
        5,
    )
    monkeypatch.setattr(
        episode_module.voe_extractor.time,
        "sleep",
        lambda seconds: sleep_calls.append(seconds),
    )
    monkeypatch.setattr(
        episode_module.voe_extractor.requests,
        "get",
        lambda url, **_kwargs: FakeResponse(
            """
            <html>
              <body>
                <p>Bitte löse das Captcha, um fortzufahren.</p>
                <form id="captcha-form"></form>
                <div class="cf-turnstile"></div>
              </body>
            </html>
            """
        ),
    )

    episode = episode_module.build_episode(
        slug="better-call-saul",
        season=1,
        episode=8,
        site="s.to",
    )

    with pytest.raises(ValueError, match="automatic backoff retries"):
        episode.get_direct_link("VOE", "German Dub")
    assert sleep_calls == [5, 10]
