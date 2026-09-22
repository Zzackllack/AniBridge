# Scope and decisions

## Product purpose

AniBridge makes supported streaming catalogs usable through Torznab and qBittorrent-compatible APIs for Prowlarr, Sonarr, and related automation. Its value is correct identity mapping, language selection, queue lifecycle, download/STRM output, naming, and reliable import. It does not need to duplicate upstream's general-purpose application.

The maintainer wants to revive the project through separable work: first a working baseline and upstream update; later catalog performance, incremental refresh, a catalog-worker experiment, and a small WebUI. This document covers only the first step.

## Why this must be independent of #119

PR #119 (`provider-catalog-index`) changes search readiness, persistence generations, scheduling, and downloader behavior. Its resource problems cannot be solved or validated by this upgrade. Combining the changes would obscure whether a regression comes from dependency drift, indexing, or protocol semantics.

Keep the catalog branch/history intact. Do not merge, rebase, cherry-pick, or redesign #119 as part of implementing this specification unless separately authorized. After the compatibility change lands, the catalog branch will need its own integration refresh and performance validation.

## Decisions

### D1 — Pin a released package

Use `aniworld==5.0.6` as the researched implementation target. Do not track upstream's `models` branch or an unbounded `>=5` range. Recheck release availability before implementation; if a newer release exists, assess the incremental diff and revise evidence rather than silently substituting it.

### D2 — Retain Python and API contracts

Keep Python 3.14 and current externally visible routes, field shapes, naming, language labels, magnet identity, and STRM modes. This is not a service rewrite. No database schema migration is expected for a dependency compatibility change.

### D3 — Upstream API availability is not runtime equivalence

Callable symbols and passing tests are necessary but insufficient. Upstream import side effects, domain selection, TLS verification, cookies, browser launches, timeout behavior, and packaging must be assessed. A returned URL is not proof of a playable/importable result.

### D4 — No automatic browser platform in this increment

The dependency now installs Patchright as a Python dependency; that does not imply browser automation is supported in AniBridge. Do not silently download Chromium or start a browser during ordinary searches. Challenge-protected requests must terminate with a useful failure within a bounded period. Persistent browser profiles, interactive verification, session management, and their WebUI are separate work.

If an upstream extractor can enter browser solving, introduce a tested boundary or select a non-browser extraction path; do not rely on the absence of a binary as the product's control mechanism. Retain the package dependency graph intact rather than omitting required dependencies using `--no-deps`.

### D5 — Keep transport policy explicit

Preserve configured catalog base URLs and certificate verification. Upstream 5.0.6's s.to transport can rewrite hosts and fall back to a hard-coded IP with `verify=False`; this is a concrete newly introduced behavior, not a hypothetical warning. Do not ship that behavior unnoticed. See the implementation design for a contained alternative using existing local parsing.

### D6 — Do not advertise #158 as fixed

Reporter evidence: changing the public IP made the same container/configuration/episode succeed. The failing URL remained at `serienstream.to/r`. That supports IP-dependent protection but does not identify the exact response or challenge provider. The maintainer observed extra CAPTCHA prompts on NordVPN; that is context, not a captured reproduction of the reporter's request.

Both old and new dependencies work from the research machine. An upgrade may improve some paths; it is not an established repair for the reported failure. Avoid saying the block is definitively at VOE when the last URL is on Serienstream.

### D7 — Separate operational and catalog state

No catalog snapshots or new index schema are needed here. Upstream-owned configuration/session files should live in a documented writable directory under AniBridge's persistent data area, with deliberate handling of existing upstream configuration. Do not mutate process HOME merely to make a library work if its supported configuration-directory option is sufficient.

### D8 — Preserve release channels

Python installation, Docker amd64/arm64, and existing packaged binaries have distinct validation needs. A successful local macOS environment is not a substitute for those checks. Release scripts remain authoritative; implementation must not hand-edit release versions or tags.

## Explicit non-goals

- New catalog providers (including upstream's manga or adult-content providers).
- Replacing AniBridge's download scheduling with upstream's WebUI/queue server.
- Browser-based CAPTCHA solving or a guarantee of uninterrupted scraping.
- Broad host extraction rewrites unrelated to a demonstrated compatibility problem.
- Database engine replacement, indexing refresh algorithms, new canonical matching.
- Project rename, monetization, hosted catalog publication, legal-policy changes.
- Dependency-wide modernization or cleanup of unrelated warnings.

## Smallest acceptable change

The exact pin/lock update, the minimum integration/transport changes needed to uphold the existing service boundary, corresponding configuration documentation, and tests with real installed upstream classes. A large new universal provider abstraction is not a prerequisite. Reuse `EpisodeCompat`, `hosts/bridge.py`, the local s.to parser, and existing error classes where practical.
