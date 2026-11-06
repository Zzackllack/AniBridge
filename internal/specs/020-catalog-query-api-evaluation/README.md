# Catalog query architecture

AniBridge separates central metadata collection from local search and acquisition.
The collector maintains a durable provider ledger and publishes validated read
catalogs. The metadata API answers bounded queries; local AniBridge applies
corrections, serves Torznab and runs accepted jobs.

- [Implementation contract](IMPLEMENTATION.md): boundaries and failure behavior.
- [Identities and magnets](identity.md): stable source identities and compatibility.
- [Open acceptance work](ISSUES.md): remaining engineering and release gates.
- [Server setup](../../../scripts/catalog/query_pilot/SERVER.md),
  [state-preserving updates](../../../scripts/catalog/query_pilot/WORKER_UPDATES.md)
  and [generated-media acceptance](../../../scripts/catalog/query_pilot/ACCEPTANCE.md).

Only these current documents belong here. Historical specifications, audit
matrices, measurements, PR drafts and generated evidence are local-only under
ignored `internal/local/catalog-history/`; new run output belongs under
`internal/local/`. Executable fixtures remain beside their tests.
