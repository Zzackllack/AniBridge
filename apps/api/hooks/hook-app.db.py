"""Bundle Alembic scripts loaded from disk by the packaged application."""

from PyInstaller.utils.hooks import collect_data_files


datas = collect_data_files(
    "app.db",
    includes=["migrations/**"],
    include_py_files=True,
)
