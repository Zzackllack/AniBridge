"""AniWorld metadata parser, independent of API/upstream import side effects.

Only title/season/episode links and positively labelled language offers leave
this boundary. Redirect/host URLs are deliberately discarded.
"""

import re
from dataclasses import dataclass
from html.parser import HTMLParser

from catalog_core.identity import path
from catalog_core.json_codec import require

TITLE = re.compile(r"/anime/stream/([^/]+)$")
SEASON = re.compile(r"/anime/stream/([^/]+)/(?:staffel-([0-9]+)|filme)$")
EPISODE = re.compile(
    r"/anime/stream/([^/]+)/(?:staffel-([0-9]+)/episode-([1-9][0-9]*)|filme/film-([1-9][0-9]*))$"
)
# AniWorld 5.0.6 config.py and episode.py; not interchangeable with s.to.
LANGUAGES = {"1": "de-dub", "2": "en-sub", "3": "de-sub"}


@dataclass(frozen=True)
class Link:
    path: str
    name: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class EpisodeRow:
    path: str
    title: str | None
    aliases: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    unknown_languages: int = 0


@dataclass(frozen=True)
class Page:
    links: tuple[Link, ...]
    languages: tuple[str, ...]
    unknown_languages: int
    title: str | None
    next_pages: tuple[str, ...] = ()
    year: int | None = None
    explicit_imdb: str | None = None
    aliases: tuple[str, ...] = ()
    episode_title: str | None = None
    episode_aliases: tuple[str, ...] = ()
    episodes: tuple[EpisodeRow, ...] = ()
    availability: str = "available"


class Parser(HTMLParser):
    title_pattern, season_pattern, episode_pattern = TITLE, SEASON, EPISODE
    prefix = "/anime/stream/"
    listing_root = "/animes-alphabet"
    languages_map = LANGUAGES

    def is_listing_root(self, href: str) -> bool:
        return href == self.listing_root

    def listing_target(self, href: str) -> str:
        require(
            re.fullmatch(r"/animes-alphabet(?:/[1-9][0-9]*)?", href) is not None,
            "unexpected listing pagination",
        )
        return path(href)

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.document = {"html": False, "body": False}
        self.closed = set()
        self.video_section = False
        self.links = {}
        self.next_pages = set()
        self.languages = set()
        self.unknown = set()
        self.anchor = None
        self.text = []
        self.heading = False
        self.heading_text = []
        self.title = None
        self.year = None
        self.explicit_imdb = None
        self.aliases = ()
        self.start_date = False
        self.episode_title = None
        self.episode_aliases = ()
        self.episode_tag = None
        self.episode_text = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs)
        if tag in self.document:
            require(
                not self.document[tag] and tag not in self.closed,
                "duplicate document root",
            )
            self.document[tag] = True
        if "hosterSiteVideo" in (attrs.get("class") or "").split():
            self.video_section = True
        if "episodeEnglishTitle" in (attrs.get("class") or "").split():
            self.episode_tag, self.episode_text = tag, []
        if tag == "a":
            self.anchor, self.text = attrs, []
        if tag == "h1":
            self.heading, self.heading_text = True, []
            self.aliases = tuple(
                a.strip()
                for a in (attrs.get("data-alternativetitles") or "").split(",")
                if a.strip()
            )
            require(
                len(self.aliases) <= 100
                and all(len(a.encode()) <= 512 for a in self.aliases),
                "invalid aliases",
            )
        if tag == "span" and attrs.get("itemprop") == "startDate":
            self.start_date = True
        if tag == "a" and self.start_date:
            match = re.search(r"/animes/jahr/([0-9]{4})$", attrs.get("href") or "")
            if match and 1800 <= int(match[1]) <= 2200:
                self.year = int(match[1])
        if attrs.get("data-imdb"):
            candidate = attrs["data-imdb"]
            # Optional upstream hints may be malformed. Discard that hint, not
            # an otherwise valid native series; never publish/coerce the bad ID.
            if re.fullmatch(r"tt[0-9]{7,10}", candidate):
                require(
                    self.explicit_imdb in (None, candidate),
                    "conflicting explicit IMDb IDs",
                )
                self.explicit_imdb = candidate
        if tag == "li" and attrs.get("data-link-target") and attrs.get("data-lang-key"):
            code = attrs["data-lang-key"]
            if code in self.languages_map:
                self.languages.add(self.languages_map[code])
            else:
                self.unknown.add(code)

    def handle_data(self, data: str) -> None:
        if self.episode_tag:
            self.episode_text.append(data)
        if self.anchor is not None:
            self.text.append(data)
        if self.heading:
            self.heading_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in self.document:
            require(self.document[tag], "unexpected document end")
            self.closed.add(tag)
        if tag == self.episode_tag:
            self.episode_title = " ".join("".join(self.episode_text).split()) or None
            require(
                self.episode_title is None or len(self.episode_title.encode()) <= 512,
                "episode title too large",
            )
            self.episode_tag = None
        if tag == "span":
            self.start_date = False
        if tag == "h1":
            self.heading = False
            self.title = " ".join("".join(self.heading_text).split()) or None
        if tag != "a" or self.anchor is None:
            return
        attrs, self.anchor = self.anchor, None
        href = attrs.get("href", "") or ""
        relation = (attrs.get("rel") or "").lower().split()
        if "next" in relation:
            self.next_pages.add(self.listing_target(href))
            require(len(self.next_pages) <= 100, "pagination overflow")
        elif href.startswith(
            (self.listing_root + "/", self.listing_root + "?")
        ) and not self.is_listing_root(href):
            # Unknown paging controls cannot establish a complete enumeration.
            require("prev" in relation, "unrecognized listing pagination")
        if not href.startswith(self.prefix):
            return
        href = path(href)
        if not any(
            regex.fullmatch(href)
            for regex in (self.title_pattern, self.season_pattern, self.episode_pattern)
        ):
            return
        name = " ".join("".join(self.text).split())
        require(len(name.encode()) <= 512, "title too large")
        aliases = tuple(
            piece.strip().strip("'\"")
            for piece in (attrs.get("data-alternative-title") or "").split(",")
            if piece.strip()
        )
        require(all(len(a.encode()) <= 512 for a in aliases), "alias too large")
        self.links[href] = Link(href, name, aliases)
        require(len(self.links) <= 100000, "listing overflow")


def parse(
    body: bytes, kind: str, page_path: str | None = None, *, parser_type=Parser
) -> Page:
    require(len(body) <= 16 * 1024**2, "body overflow")
    parser = parser_type()
    parser.feed(body.decode("utf-8", errors="strict"))
    parser.close()
    require(
        all(parser.document.values())
        and parser.closed == {"html", "body"}
        and not parser.rawdata.strip()
        and parser.anchor is None
        and not parser.heading,
        "incomplete HTML document",
    )
    from .episode_rows import parse_rows

    rows = (
        ()
        if kind == "listing"
        else parse_rows(
            body,
            "s.to" if parser.prefix == "/serie/" else "aniworld.to",
            parser.episode_pattern,
            page_path,
        )
    )
    for row in rows:
        parser.links[row.path] = Link(row.path, row.title or "")
    availability = "available"
    if kind == "listing":
        links = tuple(
            link
            for link in parser.links.values()
            if parser.title_pattern.fullmatch(link.path) and link.name
        )
        require(bool(links), "unexpected empty listing")
    else:
        links = tuple(
            link
            for link in parser.links.values()
            if parser.season_pattern.fullmatch(link.path)
            or parser.episode_pattern.fullmatch(link.path)
        )
        if page_path is not None and parser.episode_pattern.fullmatch(page_path):
            if hasattr(parser, "availability"):
                availability = parser.availability()
            require(
                parser.title is not None
                and (parser.video_section or availability == "unavailable"),
                "unexpected episode structure",
            )
        elif page_path is not None:
            links = tuple(
                link for link in links if link.path.startswith(page_path + "/")
            )
            require(bool(links), "parent_children_missing")
        else:
            require(
                bool(links)
                or bool(parser.languages)
                or bool(parser.unknown)
                or (parser.title is not None and parser.video_section),
                "unexpected detail structure",
            )
    return Page(
        links,
        tuple(sorted(parser.languages)),
        len(parser.unknown),
        parser.title,
        tuple(sorted(parser.next_pages)),
        parser.year,
        parser.explicit_imdb,
        parser.aliases,
        parser.episode_title,
        parser.episode_aliases,
        rows,
        availability,
    )


def coordinates(value: str) -> tuple[int, int]:
    match = EPISODE.fullmatch(value)
    require(match is not None, "invalid episode path")
    return (
        (int(match[2]), int(match[3])) if match[2] is not None else (0, int(match[4]))
    )
