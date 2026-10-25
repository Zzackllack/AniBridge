# Stable catalog identities

The executable definitions are [identity.py](../../../packages/catalog-core/src/catalog_core/identity.py)
and [magnet.py](../../../packages/catalog-core/src/catalog_core/magnet.py).
Public read-table validation lives in [compact.py](../../../packages/catalog-core/src/catalog_core/compact.py).

Let `H(parts)` be lowercase SHA-256 of an NFC-normalized UTF-8 JSON array of
strings, with `ensure_ascii=False` and separators `(',', ':')`:

- Title: `H(['ab-title-1', provider, identity_anchor])`.
- Entity: `H(['ab-entity-1', provider, identity_anchor])`.
- Release: `H(['ab-release-1', provider, entity_id, language])`.
- Mapping: `H(['ab-map-1', provider, title_id, namespace, external_id])`.
- Grab: `H(['ab-grab-1', release_id, mode])`, where mode is `download` or `strm`.
  Its first 40 hex characters are the infohash, an identifier rather than a
  content checksum. The GUID is `urn:anibridge:release:1:{release_id}:{mode}`.

The identity anchor is the first validated provider-relative path. Origins,
display names, canonical numbering, quality and publication revisions cannot
change an existing identity. Preserve anchors, aliases and earliest discovery
times across rebuilds and verified renames. Similar names alone do not prove
that two source identities are the same.

Paths have one leading slash and no authority, query, fragment, traversal,
backslash, control characters or ambiguous repeated decoding. Frozen jobs keep
their accepted source identity even when later catalog mappings change.

Language tokens describe positive provider observations: `de-dub`, `en-dub`,
`de-sub`, `en-sub`. A subtitle token does not establish audio language. Unknown
labels produce a coverage gap rather than an invented release; numeric language
codes require provider-specific fixtures.

Magnet v2 carries `xt`, display-only `dn`, `ab_v=2` and a bounded base64url
`ab_data` payload. The decoder validates the complete field set, source paths,
coordinates and recomputed identities. The hash provides identity, not access
authorization. Canonical labels are frozen at admission; conflicting evidence
must not silently select another episode.

Released `aw_*` and `sto_*` magnets remain accepted by the local compatibility
decoder. Preserve their original hashes, history, categories and output paths;
do not fabricate equivalence from equal native and canonical episode numbers.
