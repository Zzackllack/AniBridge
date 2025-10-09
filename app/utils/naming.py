from __future__ import annotations
import sys
import os
from loguru import logger
from app.utils.logger import config as configure_logger

configure_logger()

from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import json
import re
import subprocess

from app.config import SOURCE_TAG, RELEASE_GROUP
from app.utils.title_resolver import resolve_series_title

LANG_TAG_MAP = {
    "German Dub": "GER",
    "German Sub": "GER.SUB",
    "English Sub": "ENG.SUB",
}


def _safe_component(s: str) -> str:
    logger.debug(f"Sanitizing component: {s}")
    s = re.sub(r"[^A-Za-z0-9]+", ".", s.strip())
    s = re.sub(r"\.+", ".", s).strip(".")
    logger.debug(f"Sanitized component: {s}")
    return s


def _series_component(display_title: str) -> str:
    logger.debug(f"Building series component from display_title: {display_title}")
    return _safe_component(display_title)


def _map_codec_name(vcodec: Optional[str]) -> str:
    logger.debug(f"Mapping codec name: {vcodec}")
    if not vcodec:
        return "H264"
    v = vcodec.lower()
    if "hevc" in v or "h265" in v or "x265" in v:
        return "H265"
    if "av01" in v or "av1" in v:
        return "AV1"
    if "vp9" in v:
        return "VP9"
    return "H264"


def _map_height_to_quality(height: Optional[int]) -> str:
    logger.debug(f"Mapping height to quality: {height}")
    if not height:
        return "SD"
    if height >= 2160:
        return "2160p"
    if height >= 1440:
        return "1440p"
    if height >= 1080:
        return "1080p"
    if height >= 720:
        return "720p"
    if height >= 480:
        return "480p"
    return "SD"


def _probe_with_ffprobe(path: Path) -> Tuple[Optional[int], Optional[str]]:
    logger.info(f"Probing file with ffprobe: {path}")
    try:
        args = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,codec_name",
            "-of",
            "json",
            str(path),
        ]
        res = subprocess.run(args, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout or "{}")
        streams = data.get("streams") or []
        if not streams:
            logger.warning(f"No streams found in ffprobe output for {path}")
            return (None, None)
        st = streams[0]
        height = st.get("height")
        vcodec = st.get("codec_name")
        logger.debug(f"ffprobe result: height={height}, vcodec={vcodec}")
        return (int(height) if height else None, str(vcodec) if vcodec else None)
    except Exception as e:
        logger.error(f"ffprobe failed for {path}: {e}")
        return (None, None)


def quality_from_info(info: Dict[str, Any]) -> Tuple[Optional[int], Optional[str]]:
    logger.debug(f"Extracting quality from info dict: {info}")
    height = None
    vcodec = None

    # 1) top-level
    height = info.get("height") or height
    vcodec = info.get("vcodec") or vcodec

    # 2) requested_downloads (häufiger)
    req = info.get("requested_downloads") or []
    if req:
        r0 = req[0]
        height = r0.get("height") or height
        vcodec = r0.get("vcodec") or vcodec

    # 3) formats (fallback)
    if not height or not vcodec:
        fmts = info.get("formats") or []
        # nimm best format
        best = None
        for f in fmts:
            if f.get("vcodec") and f.get("height"):
                if not best or (f.get("height") or 0) > (best.get("height") or 0):
                    best = f
        if best:
            height = height or best.get("height")
            vcodec = vcodec or best.get("vcodec")

    logger.debug(f"Extracted: height={height}, vcodec={vcodec}")
    return (int(height) if height else None, str(vcodec) if vcodec else None)


def build_release_name(
    *,
    series_title: str,
    season: Optional[int],
    episode: Optional[int],
    absolute_number: Optional[int] = None,
    height: Optional[int],
    vcodec: Optional[str],
    language: str,
    source_tag: str = SOURCE_TAG,
    release_group: str = RELEASE_GROUP,
) -> str:
    logger.info(
        f"Building release name for series_title={series_title}, season={season}, episode={episode}, height={height}, vcodec={vcodec}, language={language}"
    )
    series_part = _series_component(series_title)
    if absolute_number is not None:
        se_part = f"ABS{int(absolute_number):03d}"
    else:
        se_part = (
            f"S{int(season):02d}E{int(episode):02d}"
            if (season is not None and episode is not None)
            else ""
        )
    qual_part = _map_height_to_quality(height)
    codec_part = _map_codec_name(vcodec)
    lang_part = LANG_TAG_MAP.get(language, _safe_component(language))

    base = ".".join(
        [
            p
            for p in [
                series_part,
                se_part,
                qual_part,
                source_tag,
                codec_part,
                lang_part,
            ]
            if p
        ]
    )
    group = release_group.strip()
    if group:
        base = f"{base}-{group.upper()}"
    logger.success(f"Release name built: {base}")
    return base


def rename_to_release(
    *,
    path: Path,
    info: Optional[Dict[str, Any]],
    slug: Optional[str],
    season: Optional[int],
    episode: Optional[int],
    language: str,
    absolute_number: Optional[int] = None,
) -> Path:
    logger.info(f"Renaming file to release schema: {path}")
    # 1) Serien-Titel bestimmen
    display_title = None
    if slug:
        display_title = resolve_series_title(slug)
    if not display_title and slug:
        display_title = slug.replace("-", " ").title()
    if not display_title:
        display_title = "Episode"

    # 2) Quali/Codec
    h, vc = (None, None)
    if info:
        h, vc = quality_from_info(info)
    if not h or not vc:
        hh, vcc = _probe_with_ffprobe(path)
        h = h or hh
        vc = vc or vcc

    # 3) Neuen Namen bauen
    release = build_release_name(
        series_title=display_title,
        season=season,
        episode=episode,
        absolute_number=absolute_number,
        height=h,
        vcodec=vc,
        language=language,
    )

    new_path = path.with_name(f"{release}{path.suffix.lower()}")
    if new_path.exists() and new_path != path:
        i = 2
        base = new_path.stem
        while new_path.exists():
            new_path = path.with_name(f"{base}.{i}{path.suffix.lower()}")
            i += 1

    if new_path != path:
        logger.info(f"Renaming {path} to {new_path}")
        path.rename(new_path)
    else:
        logger.info(f"No rename needed for {path}")
    return new_path
