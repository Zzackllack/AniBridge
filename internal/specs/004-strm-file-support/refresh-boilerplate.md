# STRM “Dead Link” / Refresh Boilerplate (Not Implemented)

This document intentionally **does not change runtime behavior**. It’s a sketch for a future feature where AniBridge can detect/refresh dead `.strm` URLs.

## Why “dead link” refresh matters

In the current STRM implementation, the `.strm` contains the **resolved provider direct URL**. Some providers issue URLs that expire (tokens, short TTLs, geo constraints). When that happens, playback fails until the `.strm` is regenerated.

## Clarification question 4 (Sonarr sorting)

Sonarr doesn’t “understand” STRM as a special thing when it’s choosing releases. It ranks/filters releases using things like:

- quality profile (e.g., 1080p preferred),
- “size” bounds per quality,
- preferred words / release groups,
- and sometimes heuristics around seeding/peers.

Examples:

- If STRM entries report a tiny size (e.g., 1KB), Sonarr might reject them due to minimum size rules.
- If STRM entries report a normal “episode-sized” length, Sonarr might pick them without you intending it.

Current behavior: STRM items use the same heuristic `enclosure length` as non-STRM items (to avoid rejection by size filters) and keep the same quality tags in the title (plus `[STRM]`).

## “Dead link” scaffolding idea (DB mapping) — for later

Goal: persist enough info so AniBridge can later offer something like:

- “refresh this `.strm`” endpoint/CLI, or
- automatic refresh when a `.strm` is played (if a future proxy/stream endpoint exists).

### Minimal data to store

- `strm_path` (where the `.strm` file is on disk)
- `resolved_url` (the last provider URL written)
- `resolved_at` (timestamp)
- Episode identity:
  - `slug`, `season`, `episode`, `language`, `site`
  - `provider_used` (optional)

### Suggested table (SQLModel) — NOT wired into app.db.models

Do **not** copy this into `app/db/models.py` yet unless you also want to handle migrations and runtime table creation.

```py
# from __future__ import annotations
#
# from datetime import datetime, timezone
# from typing import Optional
#
# from sqlmodel import Field
# from app.db.models import ModelBase  # important: reuse private registry
#
#
# def _utcnow() -> datetime:
#     return datetime.now(timezone.utc)
#
#
# class StrmUrlMapping(ModelBase, table=True):
#     \"\"\"Future: track which provider URL was written into which .strm file.\"\"\"
#
#     # Using a dedicated id avoids composite PK churn if schema changes.
#     id: str = Field(primary_key=True, index=True)
#
#     # Episode identity
#     slug: str = Field(index=True)
#     season: int = Field(index=True)
#     episode: int = Field(index=True)
#     language: str = Field(index=True)
#     site: str = Field(default="aniworld.to", index=True)
#
#     # Output + URL
#     strm_path: str = Field(index=True)
#     resolved_url: str
#     provider_used: Optional[str] = None
#
#     resolved_at: datetime = Field(default_factory=_utcnow, index=True)
#
#     # Optional future fields:
#     # - last_played_at
#     # - refresh_count
#     # - last_http_status
#     # - last_error
```

### Suggested write points (future, NOT implemented)

- When STRM job finishes writing `.strm`:
  - insert/update mapping row for (`strm_path`) and episode identity.
- If a future “refresh” endpoint exists:
  - re-resolve URL, rewrite `.strm`, update row.

### Suggested “dead link” detection strategies (future)

- Simple: HEAD/GET the URL and consider it dead on 4xx/5xx/timeouts.
- Better: allow a small retry window; treat 403/451/429 differently.
- If proxy/VPN is involved: “dead” might be geo/rate-limit, not expiry.
