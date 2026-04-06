from pathlib import Path


def get_version() -> str:
    here = Path(__file__).resolve().parents[1]
    vfile = here.joinpath("VERSION")
    if vfile.exists():
        return vfile.read_text().strip()
    # fallback to package metadata in pyproject
    try:
        from importlib.metadata import version as _version

        return _version("anibridge")
    except Exception:
        return "0.0.0"


__version__ = get_version()
