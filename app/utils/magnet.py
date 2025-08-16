from __future__ import annotations
from typing import Dict
from loguru import logger
import os
import sys
import hashlib
import urllib.parse

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logger.remove()
logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)


def _hash_id(slug: str, season: int, episode: int, language: str) -> str:
    logger.debug(
        f"Hashing ID with slug={slug}, season={season}, episode={episode}, language={language}"
    )
    h = hashlib.sha1(
        f"{slug}|{season}|{episode}|{language}".encode("utf-8")
    ).hexdigest()
    logger.info(f"Generated hash: {h}")
    return h


def build_magnet(
    *,
    title: str,
    slug: str,
    season: int,
    episode: int,
    language: str,
    provider: str | None = None,
) -> str:
    """
    Synthetischer Magnet mit notwendiger Payload für den Shim.
    """
    logger.debug(
        f"Building magnet for title='{title}', slug='{slug}', season={season}, episode={episode}, language='{language}', provider='{provider}'"
    )
    xt = f"urn:btih:{_hash_id(slug, season, episode, language)}"
    q = {
        "xt": xt,
        "dn": title,
        "aw_slug": slug,
        "aw_s": str(season),
        "aw_e": str(episode),
        "aw_lang": language,
    }
    if provider:
        q["aw_provider"] = provider
        logger.debug(f"Added provider to magnet: {provider}")
    qs = "&".join(f"{k}={urllib.parse.quote_plus(v)}" for k, v in q.items())
    magnet_uri = f"magnet:?{qs}"
    logger.success(f"Magnet URI built: {magnet_uri}")
    return magnet_uri


def parse_magnet(magnet: str) -> Dict[str, str]:
    """
    Extrahiert unsere Payload (aw_*), dn, xt.
    """
    logger.debug(f"Parsing magnet URI: {magnet}")
    if not magnet.startswith("magnet:?"):
        logger.error("Provided string is not a magnet URI")
        raise ValueError("not a magnet")
    qs = magnet[len("magnet:?") :]
    params = urllib.parse.parse_qs(qs, keep_blank_values=False, strict_parsing=False)
    flat: Dict[str, str] = {}
    for k, v in params.items():
        if not v:
            logger.warning(f"Magnet param '{k}' has no value, skipping")
            continue
        flat[k] = v[0]
        logger.debug(f"Magnet param parsed: {k}={v[0]}")
    # sanity
    for req in ("dn", "xt", "aw_slug", "aw_s", "aw_e", "aw_lang"):
        if req not in flat:
            logger.error(f"Missing required magnet param: {req}")
            raise ValueError(f"missing magnet param: {req}")
    logger.success(f"Magnet parsed successfully: {flat}")
    return flat

