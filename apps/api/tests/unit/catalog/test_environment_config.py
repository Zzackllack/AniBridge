"""Behavioral coverage for catalog configuration from environment variables."""

import json
from pathlib import Path

import pytest

from app.catalog.config import from_env


def query_settings(**overrides: str) -> dict[str, str]:
    settings = {
        "CATALOG_MODE": "query",
        "CATALOG_API_URL": "https://catalog.example/",
        "CATALOG_SOURCE_ID": "fixture-source",
        "CATALOG_API_TOKEN": "a-test-token-that-is-long-enough",
    }
    settings.update(overrides)
    return settings


def test_empty_environment_preserves_legacy_defaults() -> None:
    config = from_env({})

    assert config.mode == "legacy"
    assert config.origin == ""
    assert config.source_id == ""
    assert config.allow_private_http is False
    assert config.token_file is None


def test_query_configuration_accepts_inline_and_file_tokens(tmp_path: Path) -> None:
    inline = query_settings()
    config = from_env(inline)

    assert config.mode == "query"
    assert config.origin == "https://catalog.example/"
    assert config.source_id == "fixture-source"
    assert config.allow_private_http is False
    assert config.bearer_token() == inline["CATALOG_API_TOKEN"]
    assert inline["CATALOG_API_TOKEN"] not in repr(config)

    token_file = tmp_path / "catalog-token"
    token_file.write_text("file-token-that-is-long-enough\n", encoding="utf-8")
    file_config = from_env(
        query_settings(
            CATALOG_API_TOKEN="",
            CATALOG_API_TOKEN_FILE=str(token_file),
            CATALOG_API_URL="http://localhost/",
        )
    )
    assert file_config.mode == "query"
    assert file_config.bearer_token() == "file-token-that-is-long-enough"


def test_json_configuration_remains_compatible_and_cannot_mix_with_env(
    tmp_path: Path,
) -> None:
    token_file = tmp_path / "catalog-token"
    token_file.write_text("json-token-that-is-long-enough", encoding="utf-8")
    config_file = tmp_path / "catalog.json"
    config_file.write_text(
        json.dumps(
            {
                "mode": "query",
                "origin": "https://catalog.example",
                "source_id": "fixture-source",
                "token_file": str(token_file),
            }
        ),
        encoding="utf-8",
    )

    config = from_env({"CATALOG_CONFIG_FILE": str(config_file)})
    assert config.mode == "query"
    assert config.bearer_token() == "json-token-that-is-long-enough"

    # Blank environment values do not override or conflict with the JSON file.
    blank = from_env(
        {
            "CATALOG_CONFIG_FILE": str(config_file),
            "CATALOG_MODE": "",
            "CATALOG_SOURCE_ID": " ",
        }
    )
    assert blank.mode == "query"

    with pytest.raises(ValueError):
        from_env({"CATALOG_CONFIG_FILE": str(config_file), "CATALOG_MODE": "query"})


@pytest.mark.parametrize(
    "settings",
    [
        {"CATALOG_MODE": "legacy", "CATALOG_SOURCE_ID": "fixture-source"},
        {"CATALOG_SOURCE_ID": "fixture-source"},
        {"CATALOG_MODE": "query", "CATALOG_API_URL": "https://catalog.example"},
    ],
    ids=["legacy-with-source", "source-without-mode", "incomplete-query"],
)
def test_partial_or_conflicting_environment_configuration_is_rejected(
    settings: dict[str, str],
) -> None:
    with pytest.raises(ValueError):
        from_env(settings)


@pytest.mark.parametrize(
    "overrides",
    [
        {"CATALOG_API_URL": "https://user:password@catalog.example"},
        {"CATALOG_API_URL": "https://catalog.example/path"},
        {"CATALOG_API_URL": "http://catalog.example"},
        {"CATALOG_SOURCE_ID": "Invalid/Source"},
        {"CATALOG_MODE": "QUERY"},
        {"CATALOG_ALLOW_PRIVATE_HTTP": "maybe"},
    ],
    ids=[
        "userinfo",
        "non-root-path",
        "remote-http",
        "bad-source-id",
        "bad-mode",
        "bad-bool",
    ],
)
def test_invalid_query_settings_are_rejected(overrides: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        from_env(query_settings(**overrides))


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("true", True),
        ("FALSE", False),
        ("1", True),
        ("0", False),
        ("YeS", True),
        ("no", False),
        ("ON", True),
        ("off", False),
        ("", False),
    ],
)
def test_private_http_setting_uses_strict_boolean_values(
    value: str, valid: bool
) -> None:
    config = from_env(query_settings(CATALOG_ALLOW_PRIVATE_HTTP=value))
    assert config.allow_private_http is valid


def test_private_http_opt_in_allows_remote_http_origin() -> None:
    config = from_env(
        query_settings(
            CATALOG_API_URL="http://catalog.example",
            CATALOG_ALLOW_PRIVATE_HTTP="yes",
        )
    )

    assert config.origin == "http://catalog.example"
    assert config.allow_private_http is True


def test_token_constraints_and_exclusive_sources(tmp_path: Path) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("a-file-token-that-is-long-enough", encoding="utf-8")
    for invalid_token in (
        "too-short",
        "x" * 513,
        "token-with\ncontrol",
        "token-with-λ-unicode",
    ):
        secret = invalid_token
        with pytest.raises(ValueError) as error:
            from_env(query_settings(CATALOG_API_TOKEN=invalid_token))
        assert secret not in str(error.value)

    with pytest.raises(ValueError):
        from_env(
            query_settings(
                CATALOG_API_TOKEN_FILE=str(token_file),
            )
        )

    missing_token = query_settings(CATALOG_API_TOKEN="")
    with pytest.raises(ValueError):
        from_env(missing_token)


@pytest.mark.parametrize("token", ["x" * 16, "x" * 512], ids=["minimum", "maximum"])
def test_token_length_boundaries_are_accepted(token: str) -> None:
    config = from_env(query_settings(CATALOG_API_TOKEN=token))

    assert config.bearer_token() == token


def test_invalid_or_unreadable_token_file_errors_do_not_expose_details(
    tmp_path: Path,
) -> None:
    secret_content = "secret-invalid-token-content-λ"
    invalid_file = tmp_path / "invalid-token"
    invalid_file.write_text(secret_content, encoding="utf-8")

    for token_path in (invalid_file, tmp_path / "missing-token"):
        with pytest.raises(ValueError) as error:
            from_env(
                query_settings(
                    CATALOG_API_TOKEN="",
                    CATALOG_API_TOKEN_FILE=str(token_path),
                )
            )
        assert secret_content not in str(error.value)
        assert str(token_path) not in str(error.value)
