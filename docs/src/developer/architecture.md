---
title: Architecture Deep Dive
outline: deep
---

# Architecture Deep Dive

This page documents the runtime architecture and algorithms that power AniBridge's modular pipeline:

- STRM / STRM Proxy
- Torznab
- qBittorrent-compatible API
- Downloader
- Database/cache layers
- Providers (AniWorld, s.to, Megakino)
- Slug resolution and best-match logic
- Prowlarr/Sonarr integration lifecycle

[[toc]]

## System Topology

```mermaid
flowchart LR
  subgraph Arr["*arr Clients"]
    Prowlarr["Prowlarr"]
    Sonarr["Sonarr / Radarr"]
    Media["Media Server (Jellyfin/Plex/Emby)"]
  end

  subgraph AB["AniBridge (FastAPI)"]
    Main["app/main.py"]
    Torznab["/torznab/api"]
    QB["/api/v2/* (qB shim)"]
    Strm["/strm/* (STRM proxy)"]
    Legacy["/downloader/download"]
    Scheduler["app/core/scheduler.py"]
    DL["app/core/downloader/*"]
    Resolver["app/utils/title_resolver.py"]
    Specials["app/providers/aniworld/specials.py"]
    DB[("SQLite + SQLModel")]
  end

  subgraph External["External Services"]
    Ani["AniWorld"]
    Sto["s.to"]
    Mega["Megakino"]
    Sky["SkyHook (Sonarr metadata)"]
  end

  Prowlarr --> Torznab
  Sonarr --> QB
  Sonarr --> Torznab
  Media --> Strm

  Torznab --> Resolver
  Torznab --> Specials
  Torznab --> DB
  QB --> Scheduler
  Legacy --> Scheduler
  Scheduler --> DL
  Scheduler --> DB
  Strm --> DB
  Strm --> DL

  Resolver --> Ani
  Resolver --> Sto
  Resolver --> Mega
  Specials --> Sky
  DL --> Ani
  DL --> Sto
  DL --> Mega
```

## Module Boundaries

```mermaid
flowchart TB
  API["API Layer<br/>app/api/*"]
  CORE["Core Services<br/>app/core/*"]
  UTIL["Utility Layer<br/>app/utils/*"]
  PROV["Provider Layer<br/>app/providers/*"]
  DB["Persistence Layer<br/>app/db/*"]
  INFRA["Infra Layer<br/>app/infrastructure/*"]

  API --> CORE
  API --> UTIL
  API --> DB
  CORE --> UTIL
  CORE --> PROV
  CORE --> DB
  UTIL --> PROV
  INFRA --> CORE
  INFRA --> UTIL
```

## Torznab Pipeline

### Endpoint Modes

`/torznab/api` supports:

- `t=caps`
- `t=search`
- `t=movie` / `t=movie-search`
- `t=tvsearch`

### `tvsearch` Runtime Flow

```mermaid
sequenceDiagram
  autonumber
  participant C as Prowlarr/Sonarr
  participant T as Torznab API
  participant R as Title Resolver
  participant S as Specials Mapper
  participant A as Availability Cache (DB)
  participant P as Probe Quality

  C->>T: GET /torznab/api?t=tvsearch&q=...&season=...&ep=...
  T->>R: slug_from_query(q)
  R-->>T: (site, slug) or None
  T->>A: list_available_languages_cached(...)
  alt fresh cache exists
    A-->>T: candidate languages
  else cache miss/stale
    T->>T: use default site language order
  end

  loop each candidate language
    T->>A: get_availability(slug,S,E,lang,site)
    alt fresh + available
      A-->>T: cached quality/provider
    else probe needed
      T->>P: probe_episode_quality(...)
      P-->>T: available,height,codec,provider
      T->>A: upsert_availability(...)
    end
    alt unavailable on AniWorld + specials enabled
      T->>S: resolve_special_mapping_from_episode_request(...)
      S-->>T: source/alias mapping
      T->>P: probe mapped source episode
      T->>A: upsert mapped availability
    end
    T->>T: build_release_name + build_magnet
    T->>T: emit RSS item(s) (+ STRM variant if enabled)
  end
  T-->>C: RSS XML
```

### Torznab Item Construction

For each successful candidate, AniBridge builds:

- release title with `build_release_name(...)`
- magnet payload with site-specific metadata prefix (`aw_` or `sto_`)
- optional `aw_mode/sto_mode=strm` variant when STRM mode is active
- Torznab attributes (`magneturl`, `size`, `infohash`, language/subs hints)

## Slug Resolution and Best-Match Algorithm

Slug resolution is centralized in `app/utils/title_resolver.py`.

### Site Selection Strategy

1. Search primary configured sites first (`CATALOG_SITES_LIST` excluding Megakino).
2. If no good match, fallback to Megakino.
3. If a site has no alphabet index, use search-only logic for that provider.
4. For `s.to`, fallback to suggest API (`/api/search/suggest`).

### Matching Flow

```mermaid
flowchart TD
  A["Input query q"] --> B["Normalize tokens + alnum form"]
  B --> C["Iterate candidate sites"]
  C --> D{"Site has index sources?"}
  D -- "No" --> E["Search-only resolver<br/>(site-specific)"]
  D -- "Yes" --> F["Load/refresh index + alt titles"]
  F --> G["Score each slug candidate<br/>(score_title_candidate)"]
  G --> H["Track best site/slug/score"]
  E --> H
  H --> I{"best_score >= 3.5 ?"}
  I -- "Yes" --> J["Return (site, slug)"]
  I -- "No" --> K{"s.to included?"}
  K -- "Yes" --> L["Try s.to suggest API fallback"]
  K -- "No" --> M["No match"]
  L --> N{"suggest hit?"}
  N -- "Yes" --> O["Return (s.to, slug)"]
  N -- "No" --> M
```

### Score Formula

`_score_title_candidate()` combines:

- exact normalized match boost
- substring containment boost
- token F1 score
- token precision/recall
- SequenceMatcher similarity (only when F1 is high enough)

The resolver accepts a candidate when score `>= 3.5`.

## AniWorld Specials Mapping (Alias vs Source Episode)

AniWorld specials (`/filme/film-N`) can diverge from Sonarr numbering. AniBridge maps:

- source episode: what AniWorld actually hosts
- alias episode: what Sonarr expects for import parsing

```mermaid
flowchart TD
  A["Need special mapping?"] --> B["Fetch AniWorld /filme entries"]
  B --> C["Resolve TVDB ID from hints/query via SkyHook"]
  C --> D["Fetch SkyHook show payload + episodes"]
  D --> E["Pick metadata episode<br/>(query or requested S/E)"]
  E --> F["Match best AniWorld filme entry by title score"]
  F --> G{"score >= threshold?"}
  G -- "No" --> H["No mapping"]
  G -- "Yes" --> I["Return SpecialEpisodeMapping<br/>source S0E(film-index) + alias S/E"]
```

When a mapping exists:

- probing/downloading uses the source episode
- release naming/GUID adds alias markers
- Sonarr import sees alias-compatible naming

## qBittorrent API Shim Pipeline

The shim lives under `/api/v2/*` and tracks jobs through `ClientTask`.

```mermaid
sequenceDiagram
  autonumber
  participant S as Sonarr/Radarr
  participant Q as qB API Shim
  participant M as Magnet Parser
  participant Sch as Scheduler
  participant DB as DB (ClientTask + Job)
  participant D as Downloader/STRM runner

  S->>Q: POST /api/v2/torrents/add (magnet)
  Q->>M: parse_magnet()
  M-->>Q: slug, S/E, lang, site, provider, mode, hash
  Q->>Sch: schedule_download(req)
  Sch->>DB: create Job(queued)
  Sch->>D: submit runner (_run_download or _run_strm)
  Q->>DB: upsert ClientTask(hash->job_id)
  Q-->>S: "Ok."

  loop polling
    S->>Q: /sync/maindata, /torrents/info, /torrents/files, /torrents/properties
    Q->>DB: read Job + ClientTask
    Q-->>S: qB-compatible state/progress/save_path/content_path
  end
```

### Shim Surface Summary

- Auth endpoints are permissive and set/delete `SID` cookie.
- Category endpoints maintain in-memory category map.
- State is DB-backed (`ClientTask` + `Job`) rather than torrent engine backed.
- `/torrents/delete` can cancel running jobs and optionally delete result files.

## Downloader and Provider Fallback

`app/core/downloader/download.py` orchestrates download fallback.

```mermaid
flowchart TD
  A["Download request"] --> B["Normalize language"]
  B --> C{"Megakino site?"}
  C -- "Yes" --> D["Megakino resolver flow"]
  D --> E["Try preferred provider then PROVIDER_ORDER"]
  E --> F["Resolve direct URL + yt-dlp download"]
  F --> G{"Success?"}
  G -- "No" --> H["Retry next provider"]
  H --> F
  G -- "Yes" --> Z["rename_to_release -> completed"]

  C -- "No" --> I["build_episode(...)"]
  I --> J["get_direct_url_with_fallback(...)"]
  J --> K["yt-dlp download"]
  K --> N{"download failed?"}
  N -- "No" --> Z
  N -- "Yes" --> O["Retry alternate providers"]
  O --> K
```

### Provider Resolution Rules

- Preferred provider is tried first when supplied.
- Fallback order uses `PROVIDER_ORDER`.
- Language availability is validated before provider iteration.
- Megakino has dedicated sitemap/search/direct-link client flow.

## STRM Creation and STRM Proxy

### STRM Job Creation (`mode=strm`)

```mermaid
sequenceDiagram
  autonumber
  participant Q as qB Shim
  participant Sch as Scheduler
  participant SR as STRM Resolver
  participant DB as StrmUrlMapping + Job
  participant FS as Filesystem

  Q->>Sch: schedule_download(req mode=strm)
  Sch->>DB: create Job
  Sch->>SR: resolve_direct_url(identity)
  SR-->>Sch: direct_url, provider_used
  alt STRM_PROXY_MODE=proxy
    Sch->>DB: upsert StrmUrlMapping(resolved_url,...)
    Sch->>Sch: build /strm/stream URL
  else direct mode
    Sch->>Sch: use direct_url in .strm
  end
  Sch->>FS: write atomic .strm file
  Sch->>DB: Job status=completed + result_path
```

### Playback Proxy Flow (`/strm/stream`, `/strm/proxy`)

```mermaid
flowchart TD
  A["Incoming /strm/stream"] --> B["Auth check<br/>none/token/apikey"]
  B --> C["Parse identity"]
  C --> D["Resolve via memory/db cache<br/>or fresh resolver"]
  D --> E["Open upstream request"]
  E --> F{"Status in refresh set<br/>403/404/410/451/429?"}
  F -- "Yes (first attempt)" --> G["Invalidate cache + re-resolve once"]
  G --> E
  F -- "No" --> H{"HLS playlist?"}
  H -- "Yes" --> I["Rewrite playlist URIs -> /strm/proxy URLs"]
  H -- "No" --> J["Stream bytes with range/header passthrough"]
```

Key behaviors:

- signed token/apikey auth for STRM URLs (configurable)
- DB + in-memory STRM mapping cache
- retry-on-refresh-status with cache invalidation
- HLS rewrite of segments/keys/media URIs so all requests stay in AniBridge

## Persistence Model

```mermaid
erDiagram
  JOB {
    string id PK
    string status
    float progress
    int downloaded_bytes
    int total_bytes
    float speed
    int eta
    string result_path
    string source_site
    datetime created_at
    datetime updated_at
  }

  CLIENT_TASK {
    string hash PK
    string job_id
    string slug
    int season
    int episode
    string language
    string site
    string save_path
    string category
    string state
    datetime added_on
    datetime completion_on
  }

  EPISODE_AVAILABILITY {
    string slug PK
    int season PK
    int episode PK
    string language PK
    string site PK
    bool available
    int height
    string vcodec
    string provider
    datetime checked_at
  }

  STRM_URL_MAPPING {
    string site PK
    string slug PK
    int season PK
    int episode PK
    string language PK
    string provider PK
    string resolved_url
    string provider_used
    datetime resolved_at
    datetime updated_at
  }

  JOB ||--o{ CLIENT_TASK : "mirrors status for *arr"
```

### Job State Model

```mermaid
stateDiagram-v2
  [*] --> queued
  queued --> downloading
  downloading --> completed
  downloading --> failed
  downloading --> cancelled
  queued --> cancelled
```

## Provider-Specific Indexing and Resolution

| Provider | Index Strategy | Search Strategy | Direct Resolution Path |
|---|---|---|---|
| AniWorld (`aniworld.to`) | Alphabet index URL/HTML cached with TTL | Token/title score matching over index + alternatives | Build episode -> provider fallback -> yt-dlp |
| s.to (`s.to`) | Alphabet index URL/HTML cached with TTL | Same score logic, plus suggest API fallback | Build/enrich episode (`sto.v2`) -> provider fallback -> yt-dlp |
| Megakino (`megakino`) | Sitemap index cache | Native client search + slug heuristics | Megakino client resolves iframe/provider direct URL |

Notes:

- `app/providers/registry.py` is deprecated compatibility code. Use `app.providers.get_provider()` / `list_providers()`.
- Provider defaults and ordering come from `CATALOG_SITE_CONFIGS` + `PROVIDER_ORDER`.

## End-to-End Sonarr + Prowlarr Workflow

```mermaid
sequenceDiagram
  autonumber
  participant P as Prowlarr
  participant T as AniBridge Torznab
  participant S as Sonarr
  participant Q as AniBridge qB Shim
  participant Sch as Scheduler
  participant D as Downloader/STRM
  participant FS as Downloads/.strm

  P->>T: tvsearch/search query
  T-->>P: RSS items (magnet payload with metadata)
  P-->>S: forwards selected release
  S->>Q: /api/v2/torrents/add (magnet)
  Q->>Sch: schedule_download(...)
  Sch->>D: run download or strm worker
  D->>FS: write media file or .strm
  Sch-->>Q: job updates persisted

  loop import polling
    S->>Q: /sync/maindata + /torrents/info + /files + /properties
    Q-->>S: qB-compatible status/content paths
  end

  S->>S: import completed artifact
```

## Practical Debug Anchors

When debugging cross-module behavior, start in this order:

1. `app/api/torznab/api.py` for release generation logic.
2. `app/utils/title_resolver.py` for slug matching and site fallback.
3. `app/api/qbittorrent/torrents.py` for magnet intake and job enqueue.
4. `app/core/scheduler.py` for runner selection (`download` vs `strm`).
5. `app/core/downloader/download.py` for provider fallback behavior.
6. `app/api/strm.py` + `app/core/strm_proxy/*` for playback proxy behavior.
7. `app/db/models.py` for persisted state and cache freshness rules.
