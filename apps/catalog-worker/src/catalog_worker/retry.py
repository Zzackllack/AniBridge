"""Classified durable retry delays. Jitter spreads recovery without long sleeps."""

import random


def policy(
    outcome: str, attempts: int, blocks: int, retry_after: int | None
) -> tuple[int, str]:
    if outcome == "rate_limited":
        return max(
            1, min(86400, retry_after if retry_after is not None else 60)
        ), "blocked"
    if outcome == "challenge_or_block":
        return min(21600, 900 * 2 ** min(blocks, 5)), "blocked"
    if outcome == "unexpected_structure":
        return 3600, "parser_error"
    if outcome in ("not_found", "http_error"):
        return 3600, "partial"
    base = (
        min(900, 60 * 2 ** min(blocks, 4))
        if outcome == "circuit"
        else min(300, 5 * 2 ** min(attempts, 6))
    )
    return max(1, int(base * random.uniform(0.8, 1.2))), "transport_error"
