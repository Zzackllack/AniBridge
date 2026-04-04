# Contract: Torznab Search (Dual Catalogue)

## Endpoint
- **Method**: `GET`
- **Path**: `/torznab/api`
- **Query Parameters**:
  - `apikey` (string, optional) – required if indexer protection enabled.
  - `t` (string, required) – `search`, `tvsearch`, or `caps`.
  - `q` (string, optional) – freeform query.
  - `rid`, `season`, `ep`, `cat`, etc. – unchanged from current Torznab support.

## Behaviour Changes
- All breadcrumb parameters remain unchanged.
- When `t` = `search` or `tvsearch`, AniBridge SHALL:
  1. Query every enabled catalogue in parallel.
  2. Collect responses, attaching `site_id` metadata (`aniworld`, `sto`) per item.
  3. Merge results into a single feed ordered by `CatalogueSite.search_priority` (ascending value = higher rank).
  4. Retain distinct entries if the same episode exists on multiple catalogues; no collapsing across `site_id`.

## Response
- **Content Type**: `application/rss+xml`
- **Schema notes**:
  - Each `<item>` gains a new `<anibridge:sourceSite>` element containing `aniworld` or `sto`.
  - Existing elements (`title`, `description`, `link`, `enclosure`, `torznab:attr`) remain unchanged.
  - The `<torznab:attr name="magneturl">` parameter string includes `site=aniworld|sto`.

## Error Handling
- If all catalogues fail, return HTTP 503 with `<error code="900" description="All catalogues unavailable"/>`.
- If at least one catalogue succeeds, respond 200 with partial results and add `<anibridge:warning>` elements enumerating failed catalogues.
