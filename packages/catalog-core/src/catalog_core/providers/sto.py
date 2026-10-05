"""Serienstream v2 metadata only; no play URL leaves the parser.

The installed AniWorld 5.0.6 s_to models document the button language labels
and year/IMDb metadata. Unknown labels are gaps, never an AniWorld key guess.
"""

import re
from typing import ClassVar
from urllib.parse import parse_qs, urlsplit

from catalog_core.json_codec import require

from . import aniworld

TITLE = re.compile(r"/serie/([^/]+)$")
SEASON = re.compile(r"/serie/([^/]+)/staffel-([0-9]+)$")
EPISODE = re.compile(r"/serie/([^/]+)/staffel-([0-9]+)/episode-([1-9][0-9]*)$")
LABELS = {"Deutsch": "de-dub", "Englisch": "en-dub"}


class Parser(aniworld.Parser):
    title_pattern, season_pattern, episode_pattern = TITLE, SEASON, EPISODE
    prefix, listing_root = "/serie/", "/serien"
    languages_map: ClassVar[
        dict[str, str]
    ] = {}  # Legacy AniWorld data-lang-key has no meaning here.

    def is_listing_root(self, href: str) -> bool:
        return href in ("/serien", "/serien?by=alpha", "/serien?by=genre")

    def listing_target(self, href: str) -> str:
        parsed = urlsplit(href)
        query = parse_qs(parsed.query, strict_parsing=True)
        require(
            parsed.path == "/serien"
            and not parsed.netloc
            and not parsed.fragment
            and query.get("by") == ["alpha"]
            and set(query) <= {"by", "page"}
            and (
                "page" not in query
                or len(query["page"]) == 1
                and re.fullmatch(r"[1-9][0-9]{0,3}", query["page"][0]) is not None
            ),
            "unexpected listing pagination",
        )
        return "/serien?by=alpha" + (
            "&page=" + query["page"][0] if "page" in query else ""
        )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        super().handle_starttag(tag, attrs)
        values = dict(attrs)
        if (
            tag == "p"
            and self.title
            and {"small", "text-muted"} <= set((values.get("class") or "").split())
        ):
            self.year_range = True
        if (
            tag == "button"
            and values.get("data-play-url")
            and values.get("data-provider-name")
        ):
            self.video_section = True
            label = values.get("data-language-label")
            if label in LABELS:
                self.languages.add(LABELS[label])
            else:
                self.unknown.add(label or "missing")
        if tag == "a":
            href = values.get("href") or ""
            year = re.fullmatch(r"/jahr/([0-9]{4})", href)
            if year and 1800 <= int(year[1]) <= 2200:
                if getattr(self, "year_range", False):
                    # The header displays first–last broadcast years. Mapping
                    # needs the first year, not the end of the run.
                    self.year = min(self.year or int(year[1]), int(year[1]))
                else:
                    require(
                        self.year in (None, int(year[1])), "conflicting release years"
                    )
                    self.year = int(year[1])
            imdb = re.fullmatch(r"https://www.imdb.com/title/(tt[0-9]{7,12})/?", href)
            if imdb:
                require(
                    self.explicit_imdb in (None, imdb[1]),
                    "conflicting explicit IMDb IDs",
                )
                self.explicit_imdb = imdb[1]
        # s.to's English episode title is the parenthesized suffix of h2.
        if tag == "h2":
            self.episode_tag, self.episode_text = tag, []

    def handle_endtag(self, tag: str) -> None:
        if tag == "p":
            self.year_range = False
        if tag == "h2" and self.episode_tag == tag:
            text = " ".join("".join(self.episode_text).split())
            match = re.fullmatch(r"S[0-9]+E[0-9]+: .+ \(([^()]+)\)", text)
            self.episode_tag = None
            if match:
                require(len(match[1].encode()) <= 512, "episode title too large")
                require(
                    self.episode_title in (None, match[1]),
                    "conflicting episode titles",
                )
                # Comment/help headings follow the episode heading on live pages.
                # They must not erase the positively observed English title.
                self.episode_title = match[1]
        super().handle_endtag(tag)


def parse(body: bytes, kind: str, page_path: str | None = None) -> aniworld.Page:
    return aniworld.parse(body, kind, page_path, parser_type=Parser)


def coordinates(value: str) -> tuple[int, int]:
    match = EPISODE.fullmatch(value)
    require(match is not None, "invalid episode path")
    return int(match[2]), int(match[3])
