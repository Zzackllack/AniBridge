---
title: Prowlarr
outline: deep
---

# Prowlarr Integration

Configure AniBridge as a Torznab indexer in Prowlarr.

## Add Indexer

1. Prowlarr → Indexers → Add Indexer → Torznab
2. Set URL to your AniBridge Torznab endpoint:
   - `http://anibridge:8000/torznab/api`
3. If you set `INDEXER_API_KEY`, add it under “API Key”
4. Categories: include `5070` (Anime)

## Test

- Use “Test” in Prowlarr; AniBridge returns a synthetic result when `t=search` with empty `q` and `TORZNAB_RETURN_TEST_RESULT=true`.

## Tips

- Map Prowlarr’s network to reach AniBridge (`docker compose` service name or host IP)
- Ensure clean URLs aren’t required; Torznab is plain `/torznab/api` with query params

