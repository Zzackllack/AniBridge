"""Provider orchestration with bounded merging and explicit partial failures."""

import asyncio
from pathlib import Path

from catalog_core import query
from catalog_core.query_client import Client, Unavailable

from .query_local import Search


class ProviderSearch:
    """Merge finite provider pages; an unavailable provider cannot erase siblings."""

    def __init__(
        self,
        client: Client,
        database: Path,
        directory: Path,
        providers: tuple[str, ...],
    ) -> None:
        self.searches = [
            Search(client, database, directory, provider) for provider in providers
        ]
        self.active = 0

    async def search(
        self, params: dict[str, str], **options
    ) -> tuple[list[dict], int, dict[str, str]]:
        if self.active >= 8:
            raise Unavailable("search_busy")
        self.active += 1
        try:
            parsed = query.parse(params)
            window = parsed.offset + parsed.limit
            rows, total, headers, failed = [], 0, {}, []
            successful = 0
            async with asyncio.timeout(15):
                for search in self.searches:
                    category = (
                        options.get("anime_category", 5070)
                        if search.provider == "aniworld.to"
                        else 5000
                    )
                    relevant = (
                        {category, options.get("movie_category", 2000)}
                        if search.provider == "megakino"
                        else {category}
                    )
                    if parsed.categories is not None and not relevant.intersection(
                        parsed.categories
                    ):
                        continue
                    if parsed.mode == "movie" and search.provider != "megakino":
                        continue
                    try:
                        page, count, diagnostics = await search.search(
                            params, _window=window, **options
                        )
                    except Unavailable:
                        failed.append(search.provider)
                        continue
                    successful += 1
                    rows.extend(page)
                    total += count
                    headers.update(diagnostics)
            if failed:
                if successful == 0:
                    raise Unavailable("catalog_unavailable")
                headers.update(
                    {
                        "X-AniBridge-Catalog-Partial": "true",
                        "X-AniBridge-Catalog-Unavailable": ",".join(failed),
                    }
                )
            rows.sort(
                key=lambda row: (-row["first_seen_at"], row["release_id"], row["mode"])
            )
            return rows[parsed.offset : window], total, headers
        finally:
            self.active -= 1
