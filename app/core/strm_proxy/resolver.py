from __future__ import annotations

from loguru import logger

from app.config import PROVIDER_ORDER
from app.infrastructure.network import disabled_proxy_env
from app.providers.megakino.client import get_default_client
from app.core.downloader import build_episode, get_direct_url_with_fallback

from .types import StrmIdentity


def resolve_direct_url(identity: StrmIdentity) -> tuple[str, str]:
    """
    Resolve an upstream direct URL for a STRM identity, using Megakino-specific provider retries when applicable and a generic fallback otherwise.
    
    When the identity's site includes "megakino" and a slug is present, attempts to resolve via Megakino client across a prioritized list of providers (including the identity's preferred provider if set) and raises an exception if all attempts fail. For other sites or when slug is missing, builds an episode descriptor and uses the generic fallback resolver.
    
    Returns:
        tuple[str, str | None]: A pair where the first element is the resolved direct upstream URL and the second is the provider name that produced the URL, or `None` if no provider name is available.
    """
    logger.debug("Resolving STRM upstream for {}", identity.cache_key())
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