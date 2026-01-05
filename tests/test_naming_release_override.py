from pathlib import Path

from app.utils.naming import rename_to_release


def test_rename_to_release_uses_override(tmp_path: Path) -> None:
    src = tmp_path / "tempfile.mp4"
    src.write_bytes(b"test")

    override = "Avengers.Endgame.2019.SD.WEB.H264.GER-MEGAKINO"
    result = rename_to_release(
        path=src,
        info=None,
        slug="avengers-endgame",
        season=None,
        episode=None,
        language="German Dub",
        site="megakino",
        release_name_override=override,
    )

    assert result.name == f"{override}.mp4"
    assert result.exists()
    assert not src.exists()
