# 013 Season Search - Approach: Emit Season-Pack Results

## Idea

For `tvsearch` requests that specify only a season, return season-pack style releases (single item per pack), similar to many public indexers.

Examples (user-provided style):

- `The Boys S02 Eng Fre Ger Ita Por Spa 2160p WEBMux HDR10Plus HDR HEVC DDP SGF`
- `The Boys (2019) Season 02 S02 (2160p WEB-DL x265 HEVC 10bit AAC 5...`
- `The Boys (2019) Season 4 S04 (2160p AMZN WEB DL x265 HEVC 10bit DDP 5 1 Vyndros)`
- `The.Boys.S02.2160p.AMZN.WEB-DL.x265.10bit.HDR10plus.DDP5.1-aKraa`
- `The Boys S02 1080p BluRay x265 RARBG [NikaNika]`

## Why this is attractive

- Very fast result generation (few items, low probe volume).
- Behavior resembles what users see on many trackers/indexers.
- One grab can satisfy many episodes when true packs exist.

## Pros

- Excellent search responsiveness.
- Potentially better UX for full-season grabs.
- Smaller RSS payloads and lower provider load.

## Cons

- Requires true pack-level source support to be correct.
  - AniBridge currently resolves/downloads per episode, not true season bundle payloads.
- Returning synthetic pack items without real pack payloads can mislead Sonarr and break import expectations.
- Sonarr behavior for pack handling is sensitive to title parsing and payload reality; fake packs are risky.
- Pack-only output can hide per-episode availability granularity.

## Risk profile

- Performance risk: low.
- Implementation risk: medium/high if true pack download support is required.
- Correctness/integration risk: high if implemented as synthetic-only packs.

## Recommendation

Do **not** switch to pack-only output unless AniBridge can provide genuine pack semantics end-to-end (discovery, magnet payload meaning, and download/import behavior).

If explored, use a dual-mode/feature-flag strategy:

- Keep per-episode output as baseline.
- Optionally add real pack items only when pack availability is truly verified.
