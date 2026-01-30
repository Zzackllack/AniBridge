from typing import Optional
from urllib.parse import urlparse
from typing import Optional

from loguru import logger

from aniworld.models import Episode  # type: ignore

from app.config import CATALOG_SITE_CONFIGS


def build_episode(
    *,
    link: Optional[str] = None,
    slug: Optional[str] = None,
    season: Optional[int] = None,
    episode: Optional[int] = None,
    site: str = "aniworld.to",
) -> Episode:
    """
    Create an Episode from either a direct URL or a slug/season/episode triple for the specified site.

    If `link` is provided it takes precedence. The `site` argument is resolved against CATALOG_SITE_CONFIGS; if a configured `base_url` is present its network location (or trimmed base_url) is used as the Episode.site. If the created Episode has no `link`, attempt to run an internal `_auto_fill_basic_details()` helper (if present) to populate basic fields for compatibility with older aniworld versions.

    Parameters:
        link (Optional[str]): Direct episode URL; used when provided.
        slug (Optional[str]): Series identifier used with `season` and `episode` when `link` is not provided.
        season (Optional[int]): Season number paired with `slug` and `episode`.
        episode (Optional[int]): Episode number paired with `slug` and `season`.
        site (str): Host site identifier that will be resolved via CATALOG_SITE_CONFIGS to determine the Episode.site (default "aniworld.to").

    Returns:
        Episode: The constructed Episode instance.

    Raises:
        ValueError: If neither `link` nor the combination of `slug`, `season`, and `episode` are supplied.
    """
    logger.info(
        "Building episode: link={}, slug={}, season={}, episode={}, site={}",
        link,
        slug,
        season,
        episode,
        site,
    )
    ep: Optional[Episode] = None
    site_domain = site
    site_cfg = CATALOG_SITE_CONFIGS.get(site)
    base_url = None
    if site_cfg:
        base_url = site_cfg.get("base_url")
        if isinstance(base_url, str) and base_url:
            parsed = urlparse(base_url)
            if parsed.netloc:
                site_domain = parsed.netloc
            else:
                site_domain = base_url.strip().strip("/")
    if link:
        logger.debug("Using direct link for episode.")
        ep = Episode(link=link, site=site_domain)
    elif slug and season and episode:
        logger.debug("Using slug/season/episode for episode.")
        if site == "s.to" and isinstance(base_url, str) and base_url:
            from app.providers.sto.v2 import build_episode_url

            link = build_episode_url(base_url, slug, season, episode)
            ep = Episode(
                link=link, slug=slug, season=season, episode=episode, site=site_domain
            )
        else:
            ep = Episode(slug=slug, season=season, episode=episode, site=site_domain)
    else:
        logger.error(
            "Invalid episode parameters: must provide either link or (slug, season, episode)."
        )
        raise ValueError("Provide either link OR (slug, season, episode).")

    # aniworld>=3.6.4 stopped auto-populating basic details when instantiated
    # via slug/season/episode. When link stays None the provider scrape later
    # fails. Force-run the helper if available. - 19 Oct 2025
    # This btw got fixed on 21 Oct 2025 with the release of aniworld 3.7.1.
    # But keeping this if anyone still uses 3.6.4 - 3.7.0. - 26 Dec 2025
    if getattr(ep, "link", None) is None:
        logger.warning(
            "Episode link is None after init; attempting to auto-fill basic details. Are you using aniworld>=3.6.4?"
        )
        auto_basic = getattr(ep, "_auto_fill_basic_details", None)
        if callable(auto_basic):
            logger.warning(
                "Running _auto_fill_basic_details() to populate episode basics."
            )
            # Guard against the flag short-circuiting the helper.
            if getattr(ep, "_basic_details_filled", False):
                setattr(ep, "_basic_details_filled", False)
                logger.warning("Reset _basic_details_filled flag to False.")
            try:
                auto_basic()
                logger.warning("Successfully populated episode basics.")
            except Exception as err:  # pragma: no cover - defensive
                logger.warning(
                    "Failed to populate episode basics (slug={}, season={}, episode={}): {}",
                    getattr(ep, "slug", slug),
                    getattr(ep, "season", season),
                    getattr(ep, "episode", episode),
                    err,
                )
    if site == "s.to":
        try:
            from app.providers.sto.v2 import enrich_episode_from_v2_url

            if isinstance(base_url, str) and base_url:
                enrich_episode_from_v2_url(episode=ep, base_url=base_url)
        except Exception as err:
            logger.warning("Failed to enrich S.to v2 episode: {}", err)

    return ep
