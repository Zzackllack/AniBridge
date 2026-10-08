"""Explicit season-row metadata; missing labels never establish absence.

Recognized AniWorld microdata and Serienstream v2 rows are bounded positive
observations. No host hints, player URLs, inferred languages or numbering maps.
"""

import re
from html.parser import HTMLParser
from pathlib import PurePosixPath

from catalog_core.json_codec import require


class Rows(HTMLParser):
    def __init__(self, provider: str, episode_pattern) -> None:
        super().__init__(convert_charrefs=True)
        self.provider, self.pattern = provider, episode_pattern
        self.rows = {}
        self.row = None
        self.capture = None

    def handle_starttag(self, tag: str, attributes) -> None:
        attrs = dict(attributes)
        classes = (attrs.get("class") or "").split()
        if tag == "tr":
            require(self.row is None, "nested episode row")
            recognized = (
                self.provider == "aniworld.to"
                and attrs.get("itemtype") == "http://schema.org/Episode"
                or self.provider == "s.to"
                and "episode-row" in classes
            )
            if recognized:
                self.row = {
                    "paths": set(),
                    "names": [],
                    "languages": set(),
                    "unknown": set(),
                }
                click = re.fullmatch(
                    r"window.location='([^']+)'", attrs.get("onclick") or ""
                )
                if click and self.pattern.fullmatch(click[1]):
                    self.row["paths"].add(click[1])
        if self.row is None:
            return
        if tag == "a" and self.pattern.fullmatch(attrs.get("href") or ""):
            self.row["paths"].add(attrs["href"])
        if tag in ("strong", "span") and (
            self.provider == "aniworld.to"
            or {"episode-title-ger", "episode-title-eng"} & set(classes)
        ):
            self.capture = (tag, [])
        code = None
        if self.provider == "aniworld.to" and tag == "img" and "flag" in classes:
            code = PurePosixPath(attrs.get("src") or "").name.lower()
            language = {
                "german.svg": "de-dub",
                "japanese-german.svg": "de-sub",
                "japanese-english.svg": "en-sub",
            }.get(code)
        elif self.provider == "s.to" and tag == "svg" and "watch-language" in classes:
            flags = set(classes) & {"svg-flag-german", "svg-flag-english"}
            code = ",".join(sorted(flags)) or "unknown"
            language = {"svg-flag-german": "de-dub", "svg-flag-english": "en-dub"}.get(
                code
            )
        else:
            return
        if language:
            self.row["languages"].add(language)
        else:
            self.row["unknown"].add(code)

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.capture[1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.capture and tag == self.capture[0]:
            name = " ".join("".join(self.capture[1]).split())
            require(len(name.encode()) <= 512, "row title overflow")
            if name:
                self.row["names"].append(name)
            self.capture = None
        if tag != "tr" or self.row is None:
            return
        row, self.row = self.row, None
        self.capture = None
        require(len(row["paths"]) <= 1, "conflicting row paths")
        if not row["paths"]:
            return
        from .aniworld import EpisodeRow

        path = next(iter(row["paths"]))
        names = tuple(dict.fromkeys(row["names"]))
        require(len(names) <= 2, "ambiguous row names")
        record = EpisodeRow(
            path,
            names[-1] if names else None,
            names[:-1],
            tuple(sorted(row["languages"])),
            len(row["unknown"]),
        )
        require(
            path not in self.rows or self.rows[path] == record,
            "conflicting episode rows",
        )
        self.rows[path] = record
        require(len(self.rows) <= 10000, "episode row overflow")


def parse_rows(body: bytes, provider: str, episode_pattern, page_path: str | None):
    parser = Rows(provider, episode_pattern)
    parser.feed(body.decode("utf-8"))
    parser.close()
    require(parser.row is None, "incomplete episode row")
    return tuple(
        row
        for row in parser.rows.values()
        if page_path and row.path.startswith(page_path + "/")
    )
