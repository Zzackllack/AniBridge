"""Bounded recent-page hints, never a complete catalog or playable offer.

Selectors are based on the permitted 2026-10-01 pages. Ignore displayed dates:
AniWorld has day precision and neither provider exposes a durable sequence.
"""

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlsplit

from catalog_core.identity import path as normalize_path
from catalog_core.json_codec import require

from .adapters import adapter

MAX_ENTRIES = 512
VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

FLAGS = {
    "german.svg": "de-dub",
    "japanese-german.svg": "de-sub",
    "japanese-english.svg": "en-sub",
}
LABELS = {"Deutsch": "de-dub", "Englisch": "en-dub"}


@dataclass(frozen=True)
class Change:
    path: str
    title: str
    language: str | None


@dataclass(frozen=True)
class Window:
    entries: tuple[Change, ...]
    unknown_languages: int
    # Observed lack of pagination is a limitation, not an exhaustion proof.
    pagination: bool = False


def signal_path(provider: str) -> str | None:
    return "/neue-episoden" if provider in ("aniworld.to", "s.to") else None


class RecentParser(HTMLParser):
    def __init__(self, provider: str, origin: str) -> None:
        super().__init__(convert_charrefs=True)
        self.provider, self.origin = provider, urlsplit(origin)
        self.stack: list[str] = []
        self.roots: set[str] = set()
        self.closed: set[str] = set()
        self.container = 0
        self.found = False
        self.row = 0
        self.target: str | None = None
        self.languages: set[str] = set()
        self.name: list[str] = []
        self.capture = 0
        self.entries: dict[tuple[str, str | None], Change] = {}
        self.unknown = 0
        self.pagination = False
        self.rows = 0
        self.row_unknown = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        void = tag in VOID
        if not void:
            self.stack.append(tag)
            require(len(self.stack) <= 128, "recent nesting overflow")
        if tag in ("html", "body"):
            require(tag not in self.roots, "duplicate recent root")
            self.roots.add(tag)
        classes = values.get("class", "").split()
        marker = (
            "newEpisodeList" if self.provider == "aniworld.to" else "new-episodes-table"
        )
        if marker in classes:
            require(not self.found, "ambiguous recent container")
            self.found, self.container = True, len(self.stack)
        if not self.container:
            return
        if not self.row and (
            self.provider == "aniworld.to"
            and tag == "div"
            and "row" in classes
            or self.provider == "s.to"
            and tag == "tr"
        ):
            self.row = len(self.stack)
            self.target, self.languages, self.name, self.capture = None, set(), [], 0
            self.row_unknown = False
        if tag == "a":
            href = values.get("href", "")
            parsed = urlsplit(href)
            if parsed.path == "/neue-episoden" and parsed.query:
                self.pagination = True
            if adapter(self.provider).EPISODE.fullmatch(parsed.path):
                require(
                    (parsed.scheme, parsed.netloc)
                    in (("", ""), (self.origin.scheme, self.origin.netloc))
                    and not parsed.query
                    and not parsed.fragment,
                    "foreign recent episode",
                )
                require(self.row != 0, "episode outside recent row")
                require(self.target in (None, parsed.path), "ambiguous recent row")
                self.target = normalize_path(parsed.path)
                if self.provider == "s.to":
                    self.capture = len(self.stack)
        if self.row and tag == "strong" and self.provider == "aniworld.to":
            self.capture = len(self.stack)
        if self.row and tag == "img" and self.provider == "aniworld.to":
            value = values.get("data-src") or values.get("src", "")
            flag = urlsplit(value).path.rsplit("/", 1)[-1]
            if flag in FLAGS:
                self.languages.add(FLAGS[flag])
            elif "flag" in classes:
                self.row_unknown = True
        if self.row and tag == "svg" and self.provider == "s.to":
            label = values.get("title")
            if label in LABELS:
                self.languages.add(LABELS[label])
            elif label:
                self.row_unknown = True

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.name.append(data)
            require(sum(len(v) for v in self.name) <= 1024, "recent label overflow")

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID:
            return
        require(bool(self.stack) and self.stack[-1] == tag, "incomplete recent markup")
        depth = len(self.stack)
        if self.capture == depth:
            self.capture = 0
        if self.row == depth:
            if self.target:
                self.rows += 1
                require(self.rows <= MAX_ENTRIES, "recent window overflow")
                name = " ".join("".join(self.name).split())
                require(0 < len(name.encode()) <= 512, "missing recent title")
                if not self.languages or self.row_unknown:
                    self.unknown += 1
                for language in self.languages or {None}:
                    key = (self.target, language)
                    self.entries[key] = Change(self.target, name, language)
                require(len(self.entries) <= MAX_ENTRIES, "recent window overflow")
            self.row = 0
        if self.container == depth:
            self.container = 0
        if tag in ("html", "body"):
            self.closed.add(tag)
        self.stack.pop()


def parse(body: bytes, provider: str, origin: str) -> Window:
    require(signal_path(provider) is not None, "unsupported recent signal")
    require(len(body) <= 16 * 1024**2, "recent body overflow")
    parser = RecentParser(provider, origin)
    parser.feed(body.decode("utf-8", errors="strict"))
    parser.close()
    require(
        parser.found
        and parser.roots == parser.closed == {"html", "body"}
        and not parser.stack
        and not parser.rawdata.strip(),
        "incomplete recent document",
    )
    return Window(tuple(parser.entries.values()), parser.unknown, parser.pagination)
