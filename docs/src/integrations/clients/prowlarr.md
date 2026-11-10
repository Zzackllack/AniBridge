---
title: Prowlarr
outline: deep
---

# Prowlarr Integration

::: danger Legal Disclaimer
Read the [Legal and Compliance overview](/legal) before using clients. You are
responsible for ensuring lawful use.
:::

Configure AniBridge as a Torznab indexer in Prowlarr.

## Add Indexer

1. Prowlarr → Indexers → Add Indexer → Torznab
2. Set URL to your AniBridge Torznab endpoint:
   - `http://anibridge:8000/torznab/api`
3. If you set `INDEXER_API_KEY`, add it under “API Key”
4. Click the checkbox "Prefer Magnet URL"

## Test

- Legacy mode: AniBridge returns a synthetic result when `t=search` has an empty
  `q` and `TORZNAB_RETURN_TEST_RESULT=true`.
- Query mode: an empty `q` is a bounded recent page, not a synthetic test item.
  Use `t=caps`, which remains available during a metadata outage.
- If `INDEXER_API_KEY` is set, enter the same key as the Prowlarr API key.

## Tips

- Map Prowlarr’s network to reach AniBridge (`docker compose` service name or host IP)
- Ensure clean URLs aren’t required; Torznab is plain `/torznab/api` with query params
- Query mode is advanced/operator-configured and bounded. Broad searches can
  return HTTP 400 `query_too_broad`; partial provider outages are flagged in
  response headers. See [Catalog Query Mode](/guide/catalog-query).
