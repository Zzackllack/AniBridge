"""Schema-shape regressions for the generated Radarr/Prowlarr runner."""

import importlib.util
import json
from pathlib import Path

import pytest

from filmo_fixture import CANONICAL_IDS, IMDB_ID, TMDB_MOVIE_ID, canonical_mapping_rows
from prepare_filmo_auth import prepare

RUNNER_PATH = Path(__file__).with_name("run_filmo.py")
SPEC = importlib.util.spec_from_file_location("acceptance_run_filmo", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


@pytest.mark.parametrize(
    ("prowlarr", "field_names", "expected_categories"),
    [
        (
            True,
            (
                "baseUrl",
                "apiPath",
                "apiKey",
                "torrentBaseSettings.seedRatio",
                "additionalParameters",
                "vipExpiration",
                "baseSettings.limits.maxSize",
            ),
            None,
        ),
        (False, ("baseUrl", "apiPath", "apiKey", "categories"), [2000]),
    ],
)
def test_torznab_values_match_live_client_schema_shapes(
    prowlarr, field_names, expected_categories
):
    schema = {"fields": [{"name": name, "value": None} for name in field_names]}
    values = RUNNER.torznab_field_values(
        base_url="http://indexer.test",
        api_path="/api",
        api_token="fixture-token",
        prowlarr=prowlarr,
    )

    RUNNER.set_fields(schema, values)

    configured = {field["name"]: field["value"] for field in schema["fields"]}
    assert configured["baseUrl"] == "http://indexer.test"
    assert configured["apiPath"] == "/api"
    assert configured["apiKey"] == "fixture-token"
    assert configured.get("categories") == expected_categories


def test_fixture_has_reviewed_tmdb_and_imdb_mappings():
    rows = canonical_mapping_rows("fixture-title", 123)
    assert {(row[2], row[3]) for row in rows} == set(CANONICAL_IDS)
    assert {row[4:6] for row in rows} == {("synthetic-v1", "reviewed")}
    assert ("tmdb-movie", TMDB_MOVIE_ID) in CANONICAL_IDS
    assert ("imdb", IMDB_ID) in CANONICAL_IDS


def test_acceptance_requires_two_source_audio_tracks_and_external_caption():
    source = {
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "height": 720},
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "tags": {"language": "eng"},
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "tags": {"language": "deu"},
            },
        ],
        "format": {"duration": "6001", "size": "1024"},
    }
    assert RUNNER.assert_embedded_tracks(source, remuxed=False)["subtitle"] == []

    output = {
        **source,
        "streams": [
            *source["streams"],
            {
                "codec_type": "subtitle",
                "codec_name": "subrip",
                "tags": {"language": "deu"},
            },
        ],
    }
    assert RUNNER.assert_embedded_tracks(output, remuxed=True)["subtitle"] == [
        {"codec": "subrip", "language": "deu"}
    ]
    with pytest.raises(AssertionError):
        RUNNER.assert_embedded_tracks(output, remuxed=False)
    with pytest.raises(AssertionError):
        RUNNER.assert_embedded_tracks(source, remuxed=True)


def test_hls_video_preflight_must_precede_segment_download():
    RUNNER.assert_hls_video_preflight(
        [
            {"input": "hls_master", "method": "GET"},
            {"input": "hls_video_segment", "method": "HEAD"},
            {"input": "hls_video_segment", "method": "GET"},
        ]
    )
    with pytest.raises(AssertionError):
        RUNNER.assert_hls_video_preflight(
            [
                {"input": "hls_video_segment", "method": "GET"},
                {"input": "hls_video_segment", "method": "HEAD"},
            ]
        )


def test_hls_accepts_later_exact_progress_after_an_estimated_phase():
    RUNNER.assert_hls_progress_evidence(
        [
            {
                "anibridge_size_estimated": True,
                "size": 1000,
                "downloaded": 250,
                "progress": 0.25,
            },
            {
                "anibridge_size_estimated": False,
                "size": 1000,
                "downloaded": 900,
                "progress": 0.9,
            },
        ],
        [
            {
                "size": 1000,
                "sizeleft": 750,
                "fixture_events_seen": [
                    {"input": "hls_video_segment", "method": "HEAD"},
                    {"input": "hls_video_segment", "method": "GET"},
                    {"input": "hls_english_audio_segment", "method": "HEAD"},
                ],
            }
        ],
    )
    with pytest.raises(AssertionError):
        RUNNER.assert_hls_progress_evidence(
            [
                {
                    "anibridge_size_estimated": False,
                    "size": 1000,
                    "downloaded": 900,
                    "progress": 0.9,
                }
            ],
            [
                {
                    "size": 1000,
                    "sizeleft": 100,
                    "fixture_events_seen": [
                        {"input": "hls_video_segment", "method": "GET"},
                        {"input": "hls_english_audio_segment", "method": "GET"},
                    ],
                }
            ],
        )
    with pytest.raises(AssertionError, match="video-only phase"):
        RUNNER.assert_hls_progress_evidence(
            [
                {
                    "anibridge_size_estimated": True,
                    "size": 1000,
                    "downloaded": 250,
                    "progress": 0.25,
                }
            ],
            [
                {
                    "size": 1000,
                    "sizeleft": 750,
                    "fixture_events_seen": [
                        {"input": "hls_video_segment", "method": "GET"},
                        {"input": "hls_english_audio_segment", "method": "GET"},
                    ],
                }
            ],
        )


@pytest.mark.parametrize(
    ("source_id", "quality", "accepted"),
    [("84", "BluRay 720p", True), ("42", "Unknown", True), ("42", "HDTV-720p", False)],
)
def test_radarr_quality_claims_match_declared_filmo_variant(
    source_id, quality, accepted
):
    parsed = {"parsedMovieInfo": {"quality": {"quality": {"name": quality}}}}
    if accepted:
        RUNNER.assert_radarr_quality(parsed, source_id)
    else:
        with pytest.raises(AssertionError):
            RUNNER.assert_radarr_quality(parsed, source_id)


def test_radarr_import_uses_completed_scan_with_explicit_move(tmp_path):
    class Response:
        def __init__(self, value):
            self.value = value
            self.content = b"{}"

        def raise_for_status(self):
            pass

        def json(self):
            return self.value

    class Radarr:
        def __init__(self):
            self.requests = []

        def request(self, method, path, json=None):
            self.requests.append((method, path, json))
            return Response({"id": 17, "status": "queued"})

        def get(self, path, params=None):
            if path == "/command/17":
                return Response(
                    {"id": 17, "status": "completed", "result": "successful"}
                )
            if path == "/movie/10331":
                return Response({"hasFile": True})
            if path == "/moviefile":
                assert params == {"movieId": 10331}
                return Response([{"movieId": 10331, "path": "/library/movie.mkv"}])
            raise AssertionError(f"unexpected Radarr endpoint {path}")

    source = tmp_path / "downloads" / "movie.mkv"
    source.parent.mkdir()
    source.write_bytes(b"generated placeholder")
    radarr = Radarr()
    status, imported = RUNNER.import_completed_download(radarr, 10331, source, "a" * 40)

    assert radarr.requests == [
        (
            "POST",
            "/command",
            {
                "name": "DownloadedMoviesScan",
                "path": str(source.parent),
                "downloadClientId": "A" * 40,
                "importMode": "Move",
            },
        )
    ]
    assert status["status"] == "completed"
    assert imported["path"] == "/library/movie.mkv"


def test_auth_setup_writes_private_files_without_emitting_credentials(tmp_path, capsys):
    directory = prepare(tmp_path / "private-auth")
    assert directory.stat().st_mode & 0o777 == 0o700
    assert (directory / "api.env").stat().st_mode & 0o777 == 0o600
    assert (directory / "qbit.json").stat().st_mode & 0o777 == 0o444

    environment = dict(
        line.split("=", 1) for line in (directory / "api.env").read_text().splitlines()
    )
    auth = json.loads((directory / "qbit.json").read_text())
    assert auth == {
        "username": environment["QBIT_USERNAME"],
        "password": environment["QBIT_PASSWORD"],
    }
    assert len(environment["QBIT_PASSWORD"]) >= 16
    assert len(environment["QBIT_SESSION_SECRET"]) >= 32
    assert environment["QBIT_COOKIE_SECURE"] == "false"
    assert capsys.readouterr().out == ""
