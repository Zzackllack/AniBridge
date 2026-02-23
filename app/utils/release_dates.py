from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup  # type: ignore

RELEASE_AT_EXTRA_KEY = "release_at"
PROBE_INFO_RELEASE_AT_KEY = "_anibridge_release_at"
_EUROPE_BERLIN = ZoneInfo("Europe/Berlin")

_MONTH_MAP = {
    "jan": 1,
    "januar": 1,
    "january": 1,
    "feb": 2,
    "februar": 2,
    "february": 2,
    "mar": 3,
    "maerz": 3,
    "märz": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "mai": 5,
    "jun": 6,
    "juni": 6,
    "june": 6,
    "jul": 7,
    "juli": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "okt": 10,
    "oct": 10,
    "oktober": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dez": 12,
    "dec": 12,
    "dezember": 12,
    "december": 12,
}

_WEEKDAY_PREFIX_RE = re.compile(
    r"^\s*(?:"
    r"montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r")\s*,?\s*",
    re.IGNORECASE,
)
_PUBLISH_PREFIX_RE = re.compile(
    r"\b(?:veröffentlicht(?:\s+bei\s+uns|\s+am)?|published(?:\s+on)?)\b\s*[:\-]?\s*",
    re.IGNORECASE,
)
_GERMAN_DMY_RE = re.compile(
    r"(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{4})"
    r"(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{2}))?",
    re.IGNORECASE,
)
_MONTH_NAME_FIRST_RE = re.compile(
    r"(?P<month>[A-Za-zÄÖÜäöüß\.]+)\s+"
    r"(?P<day>\d{1,2}),\s*(?P<year>\d{1,4})"
    r"(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{2}))?",
    re.IGNORECASE,
)
_DAY_FIRST_MONTH_NAME_RE = re.compile(
    r"(?P<day>\d{1,2})\s+"
    r"(?P<month>[A-Za-zÄÖÜäöüß\.]+)\s+"
    r"(?P<year>\d{1,4})"
    r"(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{2}))?",
    re.IGNORECASE,
)


def _coerce_month_name(raw: str) -> Optional[int]:
    key = (raw or "").strip().lower().rstrip(".")
    return _MONTH_MAP.get(key)


def _to_utc(
    *,
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
) -> Optional[datetime]:
    if year < 1900:
        return None
    try:
        local_dt = datetime(year, month, day, hour, minute, tzinfo=_EUROPE_BERLIN)
    except ValueError:
        return None
    return local_dt.astimezone(timezone.utc)


def parse_release_datetime_text(raw_text: str) -> Optional[datetime]:
    cleaned = str(raw_text or "").replace("\xa0", " ")
    cleaned = cleaned.replace("|", " ")
    cleaned = cleaned.strip()
    if not cleaned:
        return None

    cleaned = _PUBLISH_PREFIX_RE.sub("", cleaned)
    cleaned = _WEEKDAY_PREFIX_RE.sub("", cleaned)
    cleaned = re.sub(r"\buhr\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return None

    m = _GERMAN_DMY_RE.search(cleaned)
    if m:
        return _to_utc(
            year=int(m.group("year")),
            month=int(m.group("month")),
            day=int(m.group("day")),
            hour=int(m.group("hour") or 0),
            minute=int(m.group("minute") or 0),
        )

    m = _MONTH_NAME_FIRST_RE.search(cleaned)
    if m:
        month = _coerce_month_name(m.group("month"))
        if month is None:
            return None
        return _to_utc(
            year=int(m.group("year")),
            month=month,
            day=int(m.group("day")),
            hour=int(m.group("hour") or 0),
            minute=int(m.group("minute") or 0),
        )

    m = _DAY_FIRST_MONTH_NAME_RE.search(cleaned)
    if m:
        month = _coerce_month_name(m.group("month"))
        if month is None:
            return None
        return _to_utc(
            year=int(m.group("year")),
            month=month,
            day=int(m.group("day")),
            hour=int(m.group("hour") or 0),
            minute=int(m.group("minute") or 0),
        )

    return None


def parse_release_at_from_html(html_text: str) -> Optional[datetime]:
    soup = BeautifulSoup(html_text or "", "html.parser")
    candidates: list[str] = []

    for text_node in soup.find_all(
        string=re.compile(r"(veröffentlicht|published)", re.IGNORECASE)
    ):
        node = text_node.parent
        if node is None:
            continue
        title_attr = str(node.get("title") or "").strip()
        if title_attr:
            candidates.append(title_attr)
        text = node.get_text(" ", strip=True)
        if text:
            candidates.append(text)
        parent = node.parent
        if parent is not None:
            parent_title = str(parent.get("title") or "").strip()
            if parent_title:
                candidates.append(parent_title)
            parent_text = parent.get_text(" ", strip=True)
            if parent_text:
                candidates.append(parent_text)
            for strong in parent.find_all("strong"):
                strong_text = strong.get_text(" ", strip=True)
                if strong_text:
                    candidates.append(strong_text)

    timed_candidates = [c for c in candidates if re.search(r"\d{1,2}:\d{2}", c)]
    for candidate in timed_candidates + candidates:
        parsed = parse_release_datetime_text(candidate)
        if parsed is not None:
            return parsed
    return None


def release_at_from_extra(extra: object) -> Optional[datetime]:
    if not isinstance(extra, dict):
        return None
    return parse_release_datetime_iso(extra.get(RELEASE_AT_EXTRA_KEY))


def parse_release_datetime_iso(raw: object) -> Optional[datetime]:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def release_at_from_probe_info(info: object) -> Optional[datetime]:
    if not isinstance(info, dict):
        return None
    return parse_release_datetime_iso(info.get(PROBE_INFO_RELEASE_AT_KEY))


def merge_extra_with_release_at(
    *,
    base_extra: Optional[dict[str, Any]],
    release_at: Optional[datetime],
) -> Optional[dict[str, Any]]:
    extra: Optional[dict[str, Any]]
    if isinstance(base_extra, dict):
        extra = dict(base_extra)
    else:
        extra = None

    if release_at is None:
        return extra

    if extra is None:
        extra = {}
    extra[RELEASE_AT_EXTRA_KEY] = release_at.astimezone(timezone.utc).isoformat()
    return extra


def add_release_at_to_probe_info(
    info: Optional[dict[str, Any]],
    release_at: Optional[datetime],
) -> Optional[dict[str, Any]]:
    if release_at is None:
        return info

    payload = dict(info) if isinstance(info, dict) else {}
    payload[PROBE_INFO_RELEASE_AT_KEY] = release_at.astimezone(timezone.utc).isoformat()
    return payload
