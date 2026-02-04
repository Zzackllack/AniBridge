from __future__ import annotations

from loguru import logger

from app.config import PROVIDER_ORDER
from app.infrastructure.network import disabled_proxy_env
from app.providers.megakino.client import get_default_client
from app.core.downloader import build_episode, get_direct_url_with_fallback

from .types import StrmIdentity


def resolve_direct_url(identity: StrmIdentity) -> tuple[str, str]:
    """
    Resolve a direct upstream URL for the given STRM identity.
    """
    with disabled_proxy_env():
        site = identity.site
        slug = identity.slug
        if "megakino" in site and slug:
            client = get_default_client()
            preferred = identity.provider or None
            provider_candidates: list[str | None] = []
            if preferred:
                provider_candidates.append(preferred)
            for prov_name in PROVIDER_ORDER:
                if prov_name not in provider_candidates:
                    provider_candidates.append(prov_name)
            if not provider_candidates:
                provider_candidates = [None]

            last_error: Exception | None = None
            for prov_name in provider_candidates:
                try:
                    direct_url, provider_used = client.resolve_direct_url(
                        slug=slug, preferred_provider=prov_name
                    )
                    logger.debug(
                        "Megakino resolved direct URL provider={} url={}",
                        provider_used,
                        direct_url,
                    )
                    return direct_url, provider_used
                except Exception as exc:
                    last_error = exc
                    continue
            raise Exception(
                f"Megakino STRM resolution failed after retries: {last_error}"
            )

        episode = build_episode(
            slug=identity.slug,
            season=identity.season,
            episode=identity.episode,
            site=site,
        )
        return get_direct_url_with_fallback(
            episode, preferred=identity.provider, language=identity.language
        )
