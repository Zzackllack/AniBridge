from __future__ import annotations
from typing import Dict
from loguru import logger
import os
import sys
import hashlib
import urllib.parse
from app.utils.logger import config as configure_logger

configure_logger()


def _site_prefix(site: str) -> str:
    return "aw" if site == "aniworld.to" else "sto"


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
    site: str = "aniworld.to",
) -> str:
    """
    Constructs a site-aware magnet URI containing metadata required by the Shim.

    Parameters:
        title (str): Display name to include as the magnet's `dn` parameter.
        slug (str): Content identifier used in the site-prefixed slug parameter.
        season (int): Season number included as the site-prefixed `s` parameter.
        episode (int): Episode number included as the site-prefixed `e` parameter.
        language (str): Language code included as the site-prefixed `lang` parameter.
        provider (str | None): Optional provider identifier included as the site-prefixed `provider` parameter when provided.
        site (str): Source site; selects the parameter prefix — `"aw"` when `"aniworld.to"`, `"sto"` otherwise.

    Returns:
        magnet_uri (str): A magnet URI that includes `xt`, `dn`, and site-prefixed metadata (slug, s, e, lang, site, and optionally provider).
    """
    logger.debug(
        f"Building magnet for title='{title}', slug='{slug}', season={season}, episode={episode}, language='{language}', provider='{provider}', site='{site}'"
    )
    xt = f"urn:btih:{_hash_id(slug, season, episode, language)}"
    # Build query params, but ensure 'xt=urn:btih:...' keeps ':' unescaped.
    # Some consumers (Prowlarr/qBittorrent) are strict and expect a literal
    # 'urn:btih:' instead of the percent-encoded variant.

    # Use site-specific prefixes
    prefix = _site_prefix(site)

    params: list[tuple[str, str]] = [
        ("xt", xt),
        ("dn", title),
        (f"{prefix}_slug", slug),
        (f"{prefix}_s", str(season)),
        (f"{prefix}_e", str(episode)),
        (f"{prefix}_lang", language),
        (f"{prefix}_site", site),  # Add site metadata
    ]
    if provider:
        params.append((f"{prefix}_provider", provider))
        logger.debug(f"Added provider to magnet: {provider}")

    # Encode each param individually; keep ':' in xt unescaped
    encoded_parts: list[str] = []
    for k, v in params:
        if k == "xt":
            enc_v = urllib.parse.quote_plus(v, safe=":")
        else:
            enc_v = urllib.parse.quote_plus(v)
        encoded_parts.append(f"{k}={enc_v}")

    magnet_uri = f"magnet:?{'&'.join(encoded_parts)}"
    logger.success(f"Magnet URI built: {magnet_uri}")
    return magnet_uri


def parse_magnet(magnet: str) -> Dict[str, str]:
    """
    Parse a magnet URI and extract its payload parameters.

    Supports payloads using either the "aw_" (aniworld) or "sto_" (s.to) prefix; defaults to "aw_" if no prefix is detected.

    Parameters:
        magnet (str): A magnet URI beginning with "magnet:?". Query parameters are parsed and flattened to single string values.

    Returns:
        Dict[str, str]: A mapping of parameter names to their single string value. The returned dict will include at minimum:
            - "dn" (display name)
            - "xt" (exact topic, e.g., "urn:btih:...")
            - "{prefix}_slug", "{prefix}_s", "{prefix}_e", "{prefix}_lang" where "{prefix}" is "aw" or "sto".

    Raises:
        ValueError: If the input does not start with "magnet:?" or if any required parameter is missing.
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

    # Determine which prefix is used while rejecting mixed usage
    prefix: str | None = None
    for key in flat.keys():
        if key.startswith("aw_"):
            if prefix and prefix != "aw":
                logger.error("Magnet contains mixed prefixes: aw_ and sto_")
                raise ValueError("mixed magnet prefixes")
            prefix = "aw"
        elif key.startswith("sto_"):
            if prefix and prefix != "sto":
                logger.error("Magnet contains mixed prefixes: aw_ and sto_")
                raise ValueError("mixed magnet prefixes")
            prefix = "sto"
    if prefix is None:
        # Backward compatibility: default to aw_ when no explicit prefix detected
        prefix = "aw"

    # Check required params
    required_params = [
        "dn",
        "xt",
        f"{prefix}_slug",
        f"{prefix}_s",
        f"{prefix}_e",
        f"{prefix}_lang",
    ]
    for req in required_params:
        if req not in flat:
            logger.error(f"Missing required magnet param: {req}")
            raise ValueError(f"missing param: {req}")

    logger.success(f"Magnet parsed successfully: {flat}")
    return flat
