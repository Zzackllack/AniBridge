# Upstream compatibility and working-baseline handoff

Research date: 2026-09-20 (Europe/Berlin). Implementation date: 2026-09-20.
Status: **implemented, locally validated, and committed; not published, deployed,
or release-approved**. Container and real-client gates remain blocked as recorded
in [implementation results](08-implementation-results.md).

## Objective

Update AniBridge's embedded `aniworld` dependency from 4.2.1 to the researched target 5.0.6, while preserving its Torznab, qBittorrent-compatible, downloader, and STRM contracts. Establish a reproducible baseline and verify the actual runtime integration before release. Another agent must be able to implement this work without the original conversation.

The research run created the specification before the branch was renamed to
`zzackllack-aux/upstream-compatibility`. The later implementation was rebased
onto remote main `1b0370915243f86c020c62bfc336aa0f46eda2c3` and committed
locally. No deployment, publishing, pushing, or GitHub comments were performed.

## Read in this order

1. [Scope and decision record](00-scope-and-decisions.md)
2. [Verified baseline and evidence](01-baseline-and-evidence.md)
3. [Upstream release and dependency changes](02-upstream-changes.md)
4. [Runtime integration and contract inventory](03-integration-contracts.md)
5. [Implementation design](04-implementation-design.md)
6. [Validation and release gates](05-validation-plan.md)
7. [Implementation sequence and handoff checklist](06-implementation-checklist.md)
8. [Sources, reproduction, and open questions](07-research-and-reproduction.md)
9. [Implementation results and remaining gates](08-implementation-results.md)

The `evidence/` directory contains sanitized experiment results, an AST import inventory, exact package hashes, and dependency changes. They are research artifacts, not production catalog data. No provider HTML, cookie jars, stream URLs, redirect tokens, or prebuilt catalogs are included.

## Executive findings

- Target release: `aniworld` 5.0.6; Python >=3.11 upstream, while AniBridge keeps Python 3.14.
- 145 tests passed on both the original frozen lock and an isolated candidate lock. Existing tests extensively stub upstream modules and are insufficient on their own.
- Real installed models, language enums, required configuration exports, and eight host extractor entry points work in both environments in targeted probes.
- Both versions resolved German VOE links for One Piece S01E01 and the issue #158 Avatar S02E01 example, and returned HTTP 200 HLS playlist prefixes. This is not a completed media download or Sonarr import.
- A pin-only upgrade does not adopt upstream's full Serienstream browser/session resolution path: AniBridge bypasses `provider_url`.
- The newer Serienstream metadata transport does become reachable and introduces automatic mirrors and an unverified-TLS raw-IP fallback. This needs an explicit compatibility boundary before shipping.
- New dependencies include `curl-cffi`, `patchright`, and `pyee`; `authlib` leaves the default dependency graph. Browser binaries and OS libraries are a separate concern.
- Docker was installed but no usable daemon was available during research. Linux images, ARM64 runtime, Windows packaging, actual browser challenges, and the complete *arr flow remain unverified.

## Implemented outcome

- The service now pins `aniworld` 5.0.6 and avoids its Serienstream raw-IP,
  unverified-TLS, configured-origin bypass by using the local parser and a
  verified bounded transport.
- VOE uses the local non-browser path, with typed challenge/transport/source
  failures, token-safe logging, public-address checks, and bounded redirects,
  retries, and HTML redirect pages.
- Upstream configuration writes are isolated under
  `ANIWORLD_INSTALL_FOLDER` without changing the process home.
- Real-installed-package subprocess tests supplement the mocked suite.
- Wheel/sdist layout and PyInstaller migration resources were corrected after
  clean-artifact smoke tests exposed existing packaging failures.
- Fresh live checks again reached HTTP 200 HLS playlists for the two recorded
  examples. This is not Sonarr import evidence and does not establish a fix for
  issue #158.

## Definition of done

A small independent implementation PR with an exact dependency pin and reviewed lockfile, bounded and explicit transport behavior, real-package contract tests, successful supported packaging checks, and recorded end-to-end evidence. It must not claim to fix #158 unless that failure condition is reproduced and corrected. It must not require catalog PR #119, a WebUI, Turso, or a public catalog service.

## Evidence vocabulary

**Observed** means executed locally in this research run. **Source-verified** means traced in the recorded checkout/tag. **Reporter evidence** means reported in the linked issue, not reproduced locally. **Proposed** means required or recommended implementation behavior. **Unverified** marks remaining release work. Test counts and versions from older conversations are historical, not substitutes for this evidence.
