# Hosted and self-hosted catalog worker

Review date: 2026-09-26 (Europe/Berlin). Status: **ready for private
implementation against the normative contracts below; not cleared for public
redistribution, hosted-default launch, or unmeasured integration claims**.
Engineering defaults are provisional limits with explicit failure gates,
not benchmarks. No product answer is currently needed to begin M0–M4.
Target release: **3.0.0**. Base: `main` at `e14a041` (AniBridge 2.6.0). PR #119 was inspected
at local head `61351bb`; it is a reference, not this design's base.

This folder is the handoff for building a separate Python catalog collector in
the AniBridge monorepo. The same worker must be deployable as a Docker service
by the maintainer or by a user. AniBridge downloads selected provider catalog
artifacts, searches its local copy, and keeps downloads and user state local.
The first intended public release covers `aniworld.to`, `s.to`, and `megakino`.

Read in order:

1. [Decisions and scope](00-decisions-and-scope.md)
2. [Current code and PR #119 evidence](01-current-state-and-reuse.md)
3. [Services and artifact contract](02-architecture-and-contract.md)
4. [Exact artifact schema and identities](09-artifact-schema-and-identities.md)
5. [Incremental collection and publication](03-collector-and-publication.md)
6. [AniBridge consumer integration](04-consumer-and-search.md)
7. [Jobs, estimates, fallback and management](08-decision-follow-up.md)
8. [Validation and release gates](05-validation-and-gates.md)
9. [Implementation sequence](06-implementation-plan.md)
10. [Evidence and remaining release decisions](07-sources-and-open-questions.md)

## Intended shape

```text
provider sites ──> catalog worker ──> versioned provider artifacts
                                           │
                                           ▼
                              AniBridge local catalog store
                                           │
                                           ▼
                              Torznab search / *arr automation

AniBridge private DB ──> jobs, availability, STRM mappings, local overrides
AniBridge live source path ──> video-host selection and download resolution
```

After a local catalog match, AniBridge itself contacts the configured provider
site to resolve the requested episode/movie and then the selected video host
(for example VOE) when a download or stream is requested. These connections
originate from the user's AniBridge instance. The worker only collects and
publishes catalog metadata; it never proxies user playback or resolves a
user's video source.

The worker has a private mutable database; the public artifacts contain only
catalog fields explicitly allowed by the publication contract. Publishing is
independent for each provider. AniBridge's existing private database is never
replaced by a downloaded artifact.

## Evidence vocabulary

- **Inspected**: present in the pinned source/tests; no execution implied.
- **Measured**: executed with recorded inputs/environment/results. Historical
  measurements are labelled separately; none establishes current behavior.
- **Decision**: accepted direction from the maintainer discussion.
- **Contract**: chosen engineering behavior to implement and validate.
- **Provisional default**: finite initial limit; experiment may require revision.
- **Gate**: required evidence before the corresponding release/deployment.
- **Open**: answer is not yet established; do not silently assume one.

This document supersedes the *distribution and refresh architecture* in PR
#119's `internal/specs/017-provider-catalog-index/03-performance.md`, which
explicitly forbids official snapshots and instead requires every instance to
index locally. That earlier document remains historical context for its memory
analysis. This folder does not supersede the unrelated upstream compatibility
specification under `018-upstream-compatibility`.

No catalog data, scraped HTML, media URLs, cookies, or secrets are included in
this specification. The private pilot and any public hosting are separate work.

## Ownership and completion

02 owns publication trust/activation; 03 collector scheduling/discovery;
04 consumer search/feed/config/upgrade; 08 local lifecycle/API/fallback/sampling;
09 schema/identity. 05 maps each to executable gates C0–C8 and 06 sequences them.
If an experiment fails a product boundary, stop that milestone and report
measured alternatives rather than silently weakening the contract.

Private implementation status and executed commands are tracked separately in
[10-implementation-evidence.md](10-implementation-evidence.md). Its linked dated
history retains earlier failures; neither file changes an acceptance criterion.

The revision closes former illustrative DDL, identity, expiry, state and API
gaps. It retains historical evidence in 01/07 and the rejected sampling
rationale in 08. Still unmeasured: resource/freshness ceilings, client handling
of unknown size/quality and RSS bursts, real provider mapping/access/host flows,
upgrade rehearsal, signing recovery and public operating cost. These gate
milestones explicitly; text coverage alone is not proof of completion.
