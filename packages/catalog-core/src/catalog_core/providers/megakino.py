"""Strict sitemap/movie metadata adapter; never resolve or publish host links.

The sitemap path layout follows the released mainline adapter. Movie detail
year anchor is verified on the supplied private-pilot page; unlabelled
players stay a coverage gap.
In particular, Movie.inLanguage is not a provider's selectable release language.
"""

import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

from defusedxml import ElementTree

from catalog_core.identity import path as normalize_path
from catalog_core.json_codec import require

from .aniworld import Link, Page

TITLE = re.compile(r"/(films|serials)/[1-9][0-9]*-([^/]+)\.html$")
SITEMAP = re.compile(r"/(?:uploads/)?sitemap[a-zA-Z0-9_-]*\.xml$")
LABELS = {
    "Deutsch": "de-dub",
    "German Dub": "de-dub",
    "English Dub": "en-dub",
    "German Sub": "de-sub",
    "English Sub": "en-sub",
}


def local_path(value: str, origin: str, aliases: tuple[str, ...] = ()) -> str:
    parsed, expected = urlsplit(value), urlsplit(origin)
    require(
        not parsed.query and not parsed.fragment and not parsed.username,
        "invalid sitemap target",
    )
    require(
        (parsed.scheme, parsed.netloc)
        in (
            ("", ""),
            (expected.scheme, expected.netloc),
            *((urlsplit(a).scheme, urlsplit(a).netloc) for a in aliases),
        ),
        "foreign sitemap target",
    )
    return normalize_path(parsed.path)


def listing(body: bytes, origin: str, aliases: tuple[str, ...] = ()) -> Page:
    # The caller enforces the body ceiling and parses in a memory-limited child.
    root = ElementTree.fromstring(
        body, forbid_dtd=True, forbid_entities=True, forbid_external=True
    )
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    require(
        root.tag in (namespace + "urlset", namespace + "sitemapindex"),
        "unexpected sitemap root",
    )
    index = root.tag == namespace + "sitemapindex"
    paths, links = set(), {}
    require(len(root) <= 100000, "sitemap overflow")
    for entry in root:
        require(
            entry.tag == namespace + ("sitemap" if index else "url"),
            "unexpected sitemap entry",
        )
        locations = entry.findall(namespace + "loc")
        require(
            len(locations) == 1 and bool(locations[0].text), "missing sitemap location"
        )
        path = local_path(locations[0].text.strip(), origin, aliases)
        if index:
            require(SITEMAP.fullmatch(path) is not None, "unexpected child sitemap")
            paths.add(path)
        elif match := TITLE.fullmatch(path):
            require(len(match[2].encode()) <= 512, "invalid discovery label")
            # A slug is only a pending discovery label; detail replaces it before
            # mapping_input exists. Never map a prettified URL as an observed name.
            links[path] = Link(path, match[2])
    require(bool(paths or links), "unexpected empty sitemap")
    return Page(tuple(links.values()), (), 0, None, tuple(sorted(paths)))


class Detail(HTMLParser):
    def __init__(self, origin: str) -> None:
        super().__init__(convert_charrefs=True)
        self.roots, self.closed = set(), set()
        self.heading = None
        self.title = None
        self.script = None
        self.records = []
        self.languages, self.unknown = set(), set()
        self.players = 0
        self.origin = origin
        self.year = None
        self.year_text = None
        self.year_link = None
        self.year_depth = 0
        self.year_scope_seen = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in ("html", "body"):
            require(tag not in self.roots, "duplicate document root")
            self.roots.add(tag)
        if tag == "div":
            if "pmovie__year" in (values.get("class") or "").split():
                require(not self.year_scope_seen, "ambiguous movie year")
                self.year_scope_seen, self.year_depth = True, 1
            elif self.year_depth:
                self.year_depth += 1
                require(self.year_depth <= 128, "movie year nesting overflow")
        if tag == "a" and self.year_depth:
            target = urlsplit(values.get("href") or "")
            year_path = re.fullmatch(r"/xfsearch/release_date/([0-9]{4})/", target.path)
            if year_path:
                require(
                    self.year is None and self.year_text is None, "ambiguous movie year"
                )
                local_path(values["href"], self.origin)
                self.year_link, self.year_text = int(year_path[1]), []
        if tag == "h1":
            require(
                self.heading is None and self.title is None, "ambiguous movie title"
            )
            self.heading = []
        if tag == "script" and values.get("type") == "application/ld+json":
            self.script = []
        if (tag == "iframe" and (values.get("src") or values.get("data-src"))) or (
            tag in ("a", "button")
            and any(
                values.get(key) for key in ("data-iframe", "data-embed", "data-player")
            )
        ):
            self.players += 1
            label = values.get("data-language-label")
            if label in LABELS:
                self.languages.add(LABELS[label])
            else:
                self.unknown.add(label or "unlabelled")

    def handle_data(self, data: str) -> None:
        if self.year_text is not None:
            # The field also contains countries/runtime. Capture only the
            # explicitly labelled year anchor, never its URL alone.
            if content := data.strip():
                self.year_text.append(content)
            require(
                sum(len(v.encode()) for v in self.year_text) <= 32,
                "movie year overflow",
            )
        if self.heading is not None:
            self.heading.append(data)
        if self.script is not None:
            self.script.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("html", "body"):
            self.closed.add(tag)
        if tag == "a" and self.year_text is not None:
            text = " ".join("".join(self.year_text).split())
            require(re.fullmatch(r"[0-9]{4}", text) is not None, "invalid movie year")
            self.year = int(text)
            require(
                1800 <= self.year <= 2200 and self.year == self.year_link,
                "invalid movie year",
            )
            self.year_text = None
        if tag == "div" and self.year_depth:
            self.year_depth -= 1
        if tag == "h1" and self.heading is not None:
            self.title = " ".join("".join(self.heading).split())
            self.heading = None
            require(
                bool(self.title) and len(self.title.encode()) <= 512, "invalid title"
            )
        if tag == "script" and self.script is not None:
            encoded = "".join(self.script)
            require(len(encoded.encode()) <= 65536, "structured metadata overflow")
            record = json.loads(encoded)
            self.records.extend(record if type(record) is list else [record])
            require(len(self.records) <= 100, "structured metadata overflow")
            self.script = None


def parse(
    body: bytes,
    kind: str,
    page_path: str | None = None,
    *,
    origin: str,
    sitemap_origins: tuple[str, ...] = (),
) -> Page:
    require(len(body) <= 16 * 1024**2, "body overflow")
    if kind == "listing":
        return listing(body, origin, sitemap_origins)
    match = TITLE.fullmatch(page_path or "")
    require(match is not None and match[1] == "films", "unsupported movie structure")
    parser = Detail(origin)
    parser.feed(body.decode("utf-8", errors="strict"))
    parser.close()
    require(
        parser.roots == parser.closed == {"html", "body"}
        and parser.heading is None
        and parser.script is None
        and parser.year_text is None
        and parser.year_depth == 0
        and not parser.rawdata.strip()
        and bool(parser.title)
        and parser.players > 0,
        "incomplete movie document",
    )
    movies = [
        record
        for record in parser.records
        if type(record) is dict and record.get("@type") == "Movie"
    ]
    require(len(movies) <= 1, "ambiguous movie metadata")
    year, imdb, aliases = None, None, ()
    if movies:
        movie = movies[0]
        if movie.get("url"):
            require(
                local_path(movie["url"], origin) == page_path, "foreign movie metadata"
            )
        if date := movie.get("datePublished"):
            require(
                type(date) is str
                and re.fullmatch(r"[0-9]{4}(?:-[0-9]{2}-[0-9]{2})?", date) is not None,
                "invalid release year",
            )
            year = int(date[:4])
            require(1800 <= year <= 2200, "invalid release year")
        same = movie.get("sameAs", [])
        same = [same] if type(same) is str else same
        require(type(same) is list and len(same) <= 100, "invalid external IDs")
        ids = {
            found[1]
            for value in same
            if type(value) is str
            and (
                found := re.fullmatch(
                    r"https://(?:www\.)?imdb\.com/title/(tt[0-9]{7,12})/?", value
                )
            )
        }
        require(len(ids) <= 1, "conflicting IMDb IDs")
        imdb = next(iter(ids), None)
        alternate = movie.get("alternateName", [])
        alternate = [alternate] if type(alternate) is str else alternate
        require(
            type(alternate) is list
            and len(alternate) <= 100
            and all(type(a) is str and 0 < len(a.encode()) <= 512 for a in alternate),
            "invalid aliases",
        )
        aliases = tuple(alternate)
    require(
        year is None or parser.year is None or year == parser.year,
        "conflicting movie year",
    )
    year = year if year is not None else parser.year
    return Page(
        (),
        tuple(sorted(parser.languages)),
        len(parser.unknown),
        parser.title,
        year=year,
        explicit_imdb=imdb,
        aliases=aliases,
    )
