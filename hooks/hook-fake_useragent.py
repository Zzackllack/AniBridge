"""PyInstaller hook for the fake_useragent package.

Ensure the package data (browsers.jsonl and related data) is bundled so
fake_useragent can find its resources at runtime when packaged by
PyInstaller.
"""

from PyInstaller.utils.hooks import collect_data_files

# Collect all data files from the fake_useragent package. This will pick up
# the 'data' subpackage containing browsers.jsonl which fake_useragent
# expects via importlib.resources.
datas = collect_data_files("fake_useragent")
