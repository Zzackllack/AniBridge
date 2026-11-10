"""Bounded, pure metadata parsing for Filmo movie pages."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

from catalog_core.identity import path
from catalog_core.json_codec import require

from .aniworld import Link, Page

MOVIE = re.compile(r"/movies/(?:[A-Za-z0-9._~-]|%[A-Fa-f0-9]{2}){1,180}$")
PAGINATION = re.compile(r"/movies(?:\?page=([1-9][0-9]{0,3}))?$")
ID = re.compile(r"[1-9][0-9]{0,15}")
YEAR = re.compile(r"(?:18|19|20|21)[0-9]{2}")

LANGUAGES = {
    "de": "deu",
    "deutsch": "deu",
    "german": "deu",
    "deu": "deu",
    "deutschen": "deu",
    "deutscher": "deu",
    "deutsches": "deu",
    "deutsche": "deu",
    "deutschem": "deu",
    "en": "eng",
    "english": "eng",
    "englisch": "eng",
    "englische": "eng",
    "englischen": "eng",
    "englischer": "eng",
    "eng": "eng",
    "ja": "jpn",
    "jpn": "jpn",
    "jap": "jpn",
    "japanese": "jpn",
    "japanisch": "jpn",
    "japanische": "jpn",
    "japanischen": "jpn",
    "日本語": "jpn",
    "it": "ita",
    "ita": "ita",
    "italian": "ita",
    "italiano": "ita",
    "italienisch": "ita",
    "es": "spa",
    "spa": "spa",
    "spanish": "spa",
    "español": "spa",
    "spanisch": "spa",
    "spanische": "spa",
    "ger": "deu",
    "french": "fra",
    "français": "fra",
    "französisch": "fra",
    "französische": "fra",
    "französischen": "fra",
    "kor": "kor",
    "korean": "kor",
    "koreanisch": "kor",
    "rus": "rus",
    "russian": "rus",
    "russisch": "rus",
    "tur": "tur",
    "turkish": "tur",
    "türkisch": "tur",
    "arabic": "ara",
    "arabisch": "ara",
    "portuguese": "por",
    "português": "por",
    "portugiesisch": "por",
    "chinese": "zho",
    "chinesisch": "zho",
    "mandarin": "zho",
    "hindi": "hin",
    "polish": "pol",
    "polnisch": "pol",
    "dutch": "nld",
    "niederländisch": "nld",
    "und": "und",
    "unknown": "und",
}
DATE_LABELS = {"release date", "release year", "erscheinungsdatum", "jahr"}
SOURCE_TOKEN = re.compile(
    r"(?<!\w)(web[\s-]*dl|webrip|web|blu[\s-]?ray|bluray|"
    r"telesync|ts|cam|dvd|hdtv)(?!\w)",
    re.IGNORECASE,
)
SOURCE_FAMILIES = {
    "webdl": "webdl",
    "webrip": "webrip",
    "web": "web",
    "bluray": "bluray",
    "telesync": "telesync",
    "ts": "telesync",
    "cam": "cam",
    "dvd": "dvd",
    "hdtv": "tv",
}
RESOLUTION = re.compile(r"(?<![0-9])([0-9]{3,4})\s*p\b", re.IGNORECASE)
VOID_TAGS = {
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


def _text(value: str) -> str:
    """Collapse HTML text whitespace."""
    return " ".join(value.split())


def _valid_label(value: str, maximum: int = 512) -> str:
    value = _text(value)
    require(len(value.encode("utf-8")) <= maximum, "Filmo label too large")
    return value


def _language_facts(label: str) -> tuple[list[str], list[str] | None, str]:
    """Read only language and role claims explicitly written in a row label."""
    audio, subtitles, roles = _language_clauses(label)
    if not audio:
        audio.add("und")
    role = next(iter(roles)) if len(roles) == 1 else "unknown"
    return sorted(audio), sorted(subtitles) if subtitles else None, role


def _language_clauses(label: str) -> tuple[set[str], set[str], set[str]]:
    """Classify language words within small clauses, allowing prefix/suffix roles."""
    audio: set[str] = set()
    subtitles: set[str] = set()
    roles: set[str] = set()
    unknown_only = _text(label).casefold() in {"und", "unknown"}
    if unknown_only:
        return {"und"}, subtitles, roles
    for clause in re.split(r"[,;/+|]+", label.casefold()):
        _classify_language_clause(clause, audio, subtitles, roles)
    return audio, subtitles, roles


def _classify_language_clause(
    clause: str, audio: set[str], subtitles: set[str], roles: set[str]
) -> None:
    """Apply role words to nearby languages without discarding duplicate tracks."""
    words = re.findall(r"[\wÀ-ÿ]+|und", clause)
    pending: list[tuple[str, str | None]] = []
    context: str | None = None

    def flush_pending(suffix_role: str | None = None) -> None:
        """Use a suffix role for its nearest language and retain other evidence."""
        last_index = len(pending) - 1
        for index, (language, declared_role) in enumerate(pending):
            role = (
                suffix_role
                if index == last_index and suffix_role is not None
                else declared_role or "audio"
            )
            (subtitles if role == "subtitle" else audio).add(language)
        pending.clear()

    for word in words:
        if word in {"audio", "spoken", "tonspur"}:
            flush_pending()
            context = "audio"
        elif word in {"dub", "dubbed", "synchronisiert"}:
            if pending:
                flush_pending("audio")
                context = None
            else:
                context = "audio"
            roles.add("dubbed")
        elif word in {
            "sub",
            "subs",
            "subtitle",
            "subtitles",
            "untertitel",
            "untertiteln",
        }:
            if pending:
                # A suffix role applies to the closest preceding language;
                # other unqualified words in the clause remain audio claims.
                flush_pending("subtitle")
                context = None
            else:
                context = "subtitle"
        elif word in {"original", "orig"}:
            roles.add("original")
            flush_pending("audio")
        elif word in LANGUAGES:
            tag = LANGUAGES[word]
            if word != "und" or _text(clause).casefold() in {"und", "unknown"}:
                pending.append((tag, context))
    flush_pending()


def _quality(labels: list[str]) -> dict[str, Any]:
    """Normalize source/resolution claims while retaining raw provider tags."""
    sources = set()
    heights = set()
    for label in labels:
        for match in SOURCE_TOKEN.finditer(label):
            source = re.sub(r"[\s-]", "", match[1].casefold())
            sources.add(SOURCE_FAMILIES[source])
        heights.update(int(match[1]) for match in RESOLUTION.finditer(label))
    source = next(iter(sources)) if len(sources) == 1 else "unknown"
    height = next(iter(heights)) if len(heights) == 1 else None
    return {"labels": labels, "source": source, "resolution": height}


def offer_metadata(
    native_id: str, host: str, language_label: str, tags: list[str]
) -> dict[str, Any]:
    """Build one stable offer record, excluding all ephemeral player data."""
    require(ID.fullmatch(native_id) is not None, "invalid Filmo offer ID")
    host = _valid_label(host, 64)
    require(bool(host), "missing Filmo offer host")
    host = {"voe": "VOE", "byse": "Byse"}.get(host.casefold(), host)
    language_label = _valid_label(language_label, 128)
    require(bool(language_label), "missing Filmo offer language")
    language_key = " ".join(
        unicodedata.normalize("NFKC", language_label).casefold().split()
    )
    host_key = unicodedata.normalize("NFKC", host).casefold()
    context = hashlib.sha256(f"{language_key}\0{host_key}".encode()).hexdigest()
    audio, subtitles, role = _language_facts(language_label)
    labels = [_valid_label(label, 64) for label in tags]
    return {
        "variant_anchor": f"{native_id}:{context}",
        "native_id": native_id,
        "host": host,
        "language_label": language_label,
        "audio_languages": audio,
        "subtitle_languages": subtitles,
        "audio_role": role,
        "subtitle_mode": "unknown",
        "quality": _quality(labels),
    }


class FilmoParser(HTMLParser):
    """Extract listing cards or declared movie-page metadata without URLs."""

    def __init__(self, origin: str, *, listing: bool) -> None:
        super().__init__(convert_charrefs=True)
        self.origin, self.listing = urlsplit(origin), listing
        self.links: dict[str, Link] = {}
        self.next_pages: set[str] = set()
        # Track card and provider wrappers separately from the permissive depth
        # used to associate nested anchors. A mismatched close must not make an
        # unfinished acquisition block look complete.
        self.open_elements: list[tuple[str, bool]] = []
        self.document = {"html": False, "body": False}
        self.closed: set[str] = set()
        self.heading_depth = 0
        self.heading_text: list[str] = []
        self.headings: list[str] = []
        self.card_depth = 0
        self.anchor: dict[str, str | None] | None = None
        self.anchor_text: list[str] = []
        self.anchor_is_card = False
        self.release_label: str | None = None
        self.release_label_text: list[str] = []
        self.release_value_text: list[str] | None = None
        self.years: set[int] = set()
        self.row_depth = 0
        self.provider_rows_seen = False
        self.provider_container_seen = False
        self.row_language = ""
        self.row_language_seen = False
        self.row_lang_text: list[str] | None = None
        self.row_lang_depth = 0
        self.chip_depth = 0
        self.chip: dict[str, str] | None = None
        self.tag_depth = 0
        self.tag_text: list[str] = []
        self.offers: list[dict[str, Any]] = []
        self.offer_index: dict[str, dict[str, Any]] = {}
        self.aliases: set[str] = set()
        self.imdb_ids: set[str] = set()

    def local_href(self, value: str) -> str:
        target = urlsplit(value)
        require(
            not target.username and not target.password and not target.fragment,
            "invalid Filmo link",
        )
        if target.scheme or target.netloc:
            require(
                target.scheme == self.origin.scheme == "https"
                and target.hostname == self.origin.hostname
                and (target.port or 443) == (self.origin.port or 443),
                "foreign Filmo link",
            )
        return target.path + ("?" + target.query if target.query else "")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        is_row = tag in {"div", "section"} and "provider-row" in classes
        is_chip = self.row_depth > 0 and "data-provider-chip" in values
        is_provider_container = "provider-rows" in classes
        is_card = (
            self.listing
            and tag in {"a", "div", "article", "li"}
            and "movie-poster-grid-card" in classes
        )
        if tag not in VOID_TAGS:
            self.open_elements.append(
                (tag, is_card or is_row or is_chip or is_provider_container)
            )
        if tag in self.document:
            require(
                not self.document[tag] and tag not in self.closed,
                "duplicate Filmo document root",
            )
            self.document[tag] = True
        if is_card or self.card_depth and tag not in VOID_TAGS:
            self.card_depth += 1
        if is_row:
            self.row_depth += 1
            self.provider_rows_seen = True
            self.row_language = ""
            self.row_language_seen = False
        elif self.row_depth and tag not in VOID_TAGS:
            self.row_depth += 1
        if is_provider_container:
            self.provider_container_seen = True
        if is_chip:
            self.chip_depth = 1
        elif self.chip_depth and tag not in VOID_TAGS:
            self.chip_depth += 1
        if tag == "a":
            href = values.get("href") or ""
            relation = (values.get("rel") or "").casefold().split()
            if self.listing and "next" in relation:
                next_path = self.local_href(href)
                match = PAGINATION.fullmatch(next_path)
                require(match is not None, "invalid Filmo pagination")
                self.next_pages.add(next_path)
                require(len(self.next_pages) <= 256, "Filmo pagination overflow")
            self.anchor = values
            self.anchor_text = []
            self.anchor_is_card = bool(self.card_depth)
        if tag == "meta":
            name = (values.get("name") or "").casefold()
            content = values.get("content") or ""
            if name in {"alternative-title", "alternate-name"} and content:
                alias = _valid_label(content)
                require(
                    alias in self.aliases or len(self.aliases) < 32,
                    "too many Filmo aliases",
                )
                self.aliases.add(alias)
            if name == "imdb" and re.fullmatch(r"tt[0-9]{7,12}", content):
                require(
                    content in self.imdb_ids or len(self.imdb_ids) < 1,
                    "conflicting Filmo IMDb IDs",
                )
                self.imdb_ids.add(content)
        if tag == "h1":
            self.heading_depth += 1
            self.heading_text = []
        if self.row_depth and "provider-row__lang" in classes:
            self.row_lang_text = []
            self.row_lang_depth = 1
        elif self.row_lang_text is not None and tag not in VOID_TAGS:
            self.row_lang_depth += 1
        if is_chip:
            require(
                self.row_language_seen and bool(self.row_language),
                "missing Filmo offer language",
            )
            native_id = values.get("data-movie-link-id") or ""
            require(ID.fullmatch(native_id) is not None, "invalid Filmo offer ID")
            host = _valid_label(values.get("aria-label") or "", 64)
            require(bool(host), "missing Filmo offer host")
            self.chip = {
                "native_id": native_id,
                "host": host,
            }
            self.tag_depth = 0
        if self.chip_depth and "provider-chip__metadata-tag" in classes:
            self.tag_depth += 1
            self.tag_text = []
        if tag == "dt":
            self.release_label = ""
            self.release_depth = 1
        if tag == "dd" and self.release_label is not None:
            self.release_value_text = []

    def handle_data(self, data: str) -> None:
        if self.heading_depth:
            self.heading_text.append(data)
        if self.anchor is not None:
            self.anchor_text.append(data)
        if self.row_lang_text is not None:
            self.row_lang_text.append(data)
        if self.tag_depth:
            self.tag_text.append(data)
        if self.release_label is not None and self.release_value_text is None:
            self.release_label_text.append(data)
        elif self.release_value_text is not None:
            self.release_value_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in self.document:
            require(self.document[tag], "unexpected Filmo document end")
            if tag in {"html", "body"}:
                require(
                    self.card_depth == 0
                    and self.row_depth == 0
                    and self.row_lang_text is None
                    and self.chip_depth == 0
                    and self.chip is None
                    and self.anchor is None
                    and self.heading_depth == 0
                    and self.release_value_text is None
                    and not any(scoped for _, scoped in self.open_elements),
                    "incomplete Filmo HTML",
                )
            self.closed.add(tag)
        for index in range(len(self.open_elements) - 1, -1, -1):
            if self.open_elements[index][0] == tag:
                require(
                    not any(scoped for _, scoped in self.open_elements[index + 1 :]),
                    "incomplete Filmo HTML",
                )
                del self.open_elements[index:]
                break
        if tag == "h1" and self.heading_depth:
            self.heading_depth -= 1
            title = _valid_label("".join(self.heading_text))
            if title:
                require(len(self.headings) < 2, "too many Filmo headings")
                self.headings.append(title)
        if tag == "a" and self.anchor is not None:
            href = self.anchor.get("href") or ""
            if self.anchor_is_card:
                href = self.local_href(href)
                target = path(href)
                require(MOVIE.fullmatch(target) is not None, "invalid Filmo movie link")
                name = _valid_label("".join(self.anchor_text))
                require(bool(name), "missing Filmo discovery name")
                self.links[target] = Link(target, name)
                require(len(self.links) <= 100000, "Filmo listing overflow")
            self.anchor = None
            self.anchor_is_card = False
        if self.card_depth and tag not in VOID_TAGS:
            self.card_depth -= 1
        if self.row_lang_text is not None and tag not in VOID_TAGS:
            self.row_lang_depth -= 1
            if self.row_lang_depth == 0:
                self.row_language = _valid_label("".join(self.row_lang_text), 128)
                require(bool(self.row_language), "missing Filmo offer language")
                self.row_language_seen = True
                self.row_lang_text = None
        if self.tag_depth and tag in {"span", "small", "strong", "b"}:
            label = _valid_label("".join(self.tag_text), 64)
            if label and self.chip is not None:
                labels = self.chip.setdefault("labels", "")
                require(
                    len(labels.splitlines()) < 16,
                    "too many Filmo quality labels",
                )
                self.chip["labels"] = "\n".join(filter(None, (labels, label)))
            self.tag_depth = 0
        if self.chip_depth and tag not in VOID_TAGS:
            self.chip_depth -= 1
            if self.chip_depth == 0 and self.chip is not None:
                labels = self.chip.get("labels", "").splitlines()
                offer = offer_metadata(
                    self.chip["native_id"],
                    self.chip["host"],
                    self.row_language,
                    labels,
                )
                variant = offer["variant_anchor"]
                prior = self.offer_index.get(variant)
                require(
                    prior is None or prior == offer, "ambiguous duplicate Filmo variant"
                )
                if prior is None:
                    self.offer_index[variant] = offer
                    self.offers.append(offer)
                require(len(self.offers) <= 10000, "Filmo offers overflow")
                self.chip = None
        if self.row_depth and tag not in VOID_TAGS:
            self.row_depth -= 1
        if tag == "dt" and self.release_label is not None:
            self.release_label = _text("".join(self.release_label_text)).casefold()
            if self.release_label not in DATE_LABELS:
                self.release_label = None
            self.release_label_text = []
        elif tag == "dd" and self.release_value_text is not None:
            value = _text("".join(self.release_value_text))
            match = YEAR.search(value)
            if self.release_label and match:
                self.years.add(int(match[0]))
            self.release_value_text = None
            self.release_label = None


def parse(
    body: bytes,
    kind: str,
    page_path: str | None = None,
    *,
    origin: str = "https://filmo.to",
) -> Page:
    """Parse one bounded listing or movie detail response."""
    require(type(body) is bytes and len(body) <= 16 * 1024**2, "body overflow")
    require(kind in {"listing", "detail"}, "unsupported Filmo page kind")
    parser = FilmoParser(origin, listing=kind == "listing")
    parser.feed(body.decode("utf-8", errors="strict"))
    parser.close()
    document_seen = any(parser.document.values()) or bool(parser.closed)
    document_complete = not document_seen or (
        parser.document == {"html": True, "body": True}
        and parser.closed == {"html", "body"}
    )
    require(
        document_complete
        and not parser.rawdata.strip()
        and parser.anchor is None
        and parser.heading_depth == 0
        and parser.row_depth == 0
        and parser.row_lang_text is None
        and parser.card_depth == 0
        and parser.chip_depth == 0
        and parser.chip is None
        and not any(scoped for _, scoped in parser.open_elements)
        and parser.release_value_text is None,
        "incomplete Filmo HTML",
    )

    if kind == "listing":
        require(bool(parser.links), "unexpected empty Filmo listing")
        return Page(
            tuple(parser.links.values()), (), 0, None, tuple(sorted(parser.next_pages))
        )

    normalized_path = path(page_path or "")
    require(
        normalized_path == page_path and MOVIE.fullmatch(normalized_path) is not None,
        "invalid Filmo detail path",
    )
    titles = set(parser.headings)
    require(len(titles) == 1, "missing or ambiguous Filmo title")
    years = parser.years
    require(len(years) <= 1, "conflicting Filmo release years")
    require(
        parser.provider_container_seen or parser.provider_rows_seen,
        "Filmo detail missing provider rows",
    )
    require(bool(parser.offers), "Filmo detail has no complete provider offers")
    require(len(parser.imdb_ids) <= 1, "conflicting Filmo IMDb IDs")
    aliases = tuple(sorted(parser.aliases - titles))
    unknown_labels = {
        " ".join(
            unicodedata.normalize("NFKC", offer["language_label"]).casefold().split()
        )
        for offer in parser.offers
        if "und" in offer["audio_languages"]
    }
    return Page(
        (),
        (),
        len(unknown_labels),
        next(iter(titles)),
        year=next(iter(years), None),
        explicit_imdb=next(iter(parser.imdb_ids), None),
        aliases=aliases,
        offers=tuple(parser.offers),
        availability="available",
    )
