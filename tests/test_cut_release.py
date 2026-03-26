import json
from pathlib import Path

from scripts.release import cut_release


def test_bump_version_semver() -> None:
    assert cut_release.bump_version("2.4.8", "patch") == "2.4.9"
    assert cut_release.bump_version("2.4.8", "minor") == "2.5.0"
    assert cut_release.bump_version("2.4.8", "major") == "3.0.0"


def test_apply_release_plan_updates_version_surfaces(tmp_path: Path) -> None:
    version_file = tmp_path / "VERSION"
    pyproject_file = tmp_path / "pyproject.toml"
    openapi_file = tmp_path / "openapi.json"
    package_file = tmp_path / "package.json"

    version_file.write_text("2.4.8\n", encoding="utf-8")
    pyproject_file.write_text('version = "2.4.8"\n', encoding="utf-8")
    openapi_file.write_text('{\n  "version": "2.4.8",\n}\n', encoding="utf-8")
    package_file.write_text('{\n  "version": "2.4.8"\n}\n', encoding="utf-8")

    original_paths = (
        cut_release.VERSION_FILE,
        cut_release.PYPROJECT_FILE,
        cut_release.OPENAPI_FILE,
        cut_release.DOCS_PACKAGE_FILE,
    )

    cut_release.VERSION_FILE = version_file
    cut_release.PYPROJECT_FILE = pyproject_file
    cut_release.OPENAPI_FILE = openapi_file
    cut_release.DOCS_PACKAGE_FILE = package_file
    try:
        plan = cut_release.ReleasePlan(
            previous_version="2.4.8",
            next_version="2.4.9",
            release_type="patch",
            release_tag="v2.4.9",
            previous_tag="v2.4.8",
            files=("VERSION", "pyproject.toml", "openapi.json", "package.json"),
        )
        cut_release.apply_release_plan(plan)
    finally:
        (
            cut_release.VERSION_FILE,
            cut_release.PYPROJECT_FILE,
            cut_release.OPENAPI_FILE,
            cut_release.DOCS_PACKAGE_FILE,
        ) = original_paths

    assert version_file.read_text(encoding="utf-8") == "2.4.9\n"
    assert pyproject_file.read_text(encoding="utf-8") == 'version = "2.4.9"\n'
    assert '"version": "2.4.9",' in openapi_file.read_text(encoding="utf-8")
    assert '"version": "2.4.9"' in package_file.read_text(encoding="utf-8")


def test_main_outputs_release_plan_json(tmp_path: Path) -> None:
    output_path = tmp_path / "release-plan.json"
    exit_code = cut_release.main(
        ["--release-type", "patch", "--output-json", str(output_path)]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["next_version"] == "2.4.9"
    assert payload["release_tag"] == "v2.4.9"
