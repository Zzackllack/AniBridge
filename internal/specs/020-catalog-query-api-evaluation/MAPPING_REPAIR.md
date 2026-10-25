# Mapping coverage and sustainable reconciliation

Implementation follow-up to spec 020, CQ-06/CQ-17/CQ-20/CQ-21. This keeps the
selected request API architecture. It does not approve a new deployment,
rate/resource increase, public default, branch merge or media acquisition.

## Problem and measured baseline

The October 14 operational recheck establishes healthy publication/query serving,
but only 65.31%/64.62% usable episode mapping for AniWorld/Serienstream. Waiting
for collection is insufficient. The subsequent
mapping diagnosis (`evidence/mapping-diagnosis-2026-10-14.json`, local-only) found:

- Zero never-checked entries in the existing matching-input queues.
- 15,280/92,506 usable episodes unresolved despite cached canonical descriptors;
  6,775/8,345 have no series match, and four Serienstream episodes lack names.
- In the three largest unresolved cohorts per provider, 4,739 names have no
  normalized match in the selected descriptor, 1,104 names are unusable and four
  repeat a source name. This is a concentrated sample, not a population estimate.
- 8,611 partially mapped series can trigger descriptor refresh after 1,800s.
  Two refreshes/hour require at least 17,222 requests/hour, against a shared
  canonical limit of 1,800/hour. Even one descriptor per series takes at least
  4.78 hours at that limit, excluding searches, failures and processing.

The scheduling bound is arithmetic, not an observed request trace. Cached
descriptor presence does not identify the exact rejection cause. Some selected
series associations or canonical data may themselves be wrong/incomplete.
Reverify current state before implementing; preserve the historical samples.

## Order of implementation

### 1. Reproducible rejection baseline

Add a bounded read-only diagnostic/replay command using the existing worker
status, state, matching and backup helpers. Read live SQLite through read-only
connections; use SQLite's consistent backup API for disposable copies. Never
copy only an active database file while ignoring its WAL. Account for copies,
scratch, logs and backups in the existing disk budget.

Distinguish work waiting for evidence from an examined mismatch. Emit bounded
counts for missing/conflicting parent IDs, missing/generic episode names, no
name/alias candidate, duplicate source names, duplicate canonical candidates,
unproved season context, occupied/conflicting coordinates, absent/incomplete
descriptors and source failures. Keep attempt/evidence times separate from cache
fetch times. Do not report an idle enrichment tick as a successful mapping.
Reuse matcher decision code so diagnostics cannot silently disagree with it.
Keep raw names, terms, URLs, HTML, credentials and IPs out of runtime diagnostics.
Small manually sanitized metadata fixtures may contain necessary episode names.

Freeze a deterministic evaluation set before tuning: top ten unresolved series
per provider plus at least twenty ordinary series per provider sampled across
languages, sizes and mapping outcomes. Split development and held-out cohorts.
Independently label at least 100 episode correspondences per provider, including
positive, truly ambiguous and impossible-with-current-evidence cases. Use
verified source/canonical metadata and IDs; neither the existing matcher nor
equal numbering is ground truth. Record selection and seeds. Do not manufacture
positive labels to meet a coverage target.

This first phase produces failing regressions and an executable baseline, then
proceeds to implementation. It is not permission for another investigation-only
handoff or a provider-wide network crawl.

### 2. Fix repeated work and admission mismatch

Separate canonical descriptor acquisition from local correspondence matching.
Fingerprint the relevant source episode/alias evidence, validated descriptor
content and matcher version. Rematch when one changes; avoid repeatedly applying
or fetching identical evidence merely because a title is partially mapped.
Reuse canonical evidence by verified namespace/ID across provider source titles
where safe; source identities and accepted correspondences remain separate.

Prioritize first attempts, newly observed/changed evidence and due real-failure
retries. Back off unchanged, persistently unresolved evidence while retaining a
bounded route to discover genuinely new canonical information. Use demonstrated
HTTP validators if supported; do not assume conditional-request support.
Missing forthcoming canonical episodes need a different policy from old stable
wording mismatches. Use the existing shared limiter and durable scheduling,
with fairness across providers and no unbounded overdue selection.

Do not raise the 30/minute canonical cap to conceal this mismatch. Demonstrate
that scheduled remote demand fits the configured budget, including retry/search
cost, with reported overdue-work age. Preserve transient backoff, Retry-After and
recovery. Local admission waits and parser errors cannot establish provider bans.
Any private schema change needs an additive migration, retained backup and tested
code rollback. New scheduler fields must not invalidate old observations/maps.

### 3. Improve demonstrated correspondence gaps

First establish that the selected canonical series is correct. Validate IDs,
source-specific aliases, year and associations before matching more episodes.
Conflicting previous assignments require explicit diagnostics/review; do not
silently repoint a source series to obtain a higher coverage percentage.

Retain verified multilingual/alternate episode names and canonical episode IDs
when available. Show their provenance and actual endpoint support. Evaluate
source-specific wording/annotation handling and unique contextual evidence on
the fixed cohorts. Reuse existing normalization/matching libraries where useful.
Approximate text similarity may generate candidates; it is not sufficient to
accept a mapping. Candidate uniqueness and independent supporting evidence are
required. Test near-identical titles, pilots/finales, specials, split/packed
seasons, duplicate provider associations and movie/series collisions.

If evaluating sequence alignment, require independent named/ID anchors and
compatible episode evidence. Test inserted/omitted episodes and specials. Native
coordinate equality, positional similarity or a unique candidate alone does
not prove correspondence. Keep source coordinates separately. Missing names
and canonical data remain explicit gaps when no safe evidence is available.

The One Piece S01E01 wording example is a required regression **investigation**:
accept it only after independently established unique evidence; otherwise show
the precise remaining blocker. Do not special-case its slug or hardcode a map.
Demonstrate gains on at least two recurring mismatch families, including held-out
series. Report accepted-map precision, unresolved/ambiguous counts, and changes
across the entire copied ledger. No global 100% mapping promise is justified.

### 4. Finish parser/retry follow-ups and client/CI checks

Reproduce CQ-20's explicit-unavailable player with a missing episode heading.
Retain useful metadata and previous releases without inventing an episode name,
audio language or release date. Identify the remaining season contract rejection
and representative unknown-language observations with bounded metadata requests
and maintained upstream source. Existing removal quarantines stay unapproved.
Do not mistake absent evidence for a removal, or endlessly treat stable parse
gaps like transient transport errors. Retain retry history and recovery on change.

Run the worker/core regressions during these fixes and add frozen project CI
jobs with an always-running final gate for PRs into `main`/`v3`. Do not change
GitHub protection settings without authorization. Keep CI work from replacing
the mapping fixes. Prepare the matching disposable-client preview upgrade and
exact rollback; changing its live image still requires separate approval.

## Completion evidence

Deliver working code, focused tests, modular multiline Conventional Commits,
updated issues/evidence and a concrete state-preserving rollout/rollback plan:

1. Baseline/candidate use the same copied state, cohorts, limits and evaluation
   labels. Publish provider-wide counts, cohort/held-out precision and recall,
   uncertainty and representative remaining blockers. Resolve the independently
   labelled uniquely resolvable cases; retain ambiguous/insufficient cases.
2. Zero incorrect accepted mappings in the independently reviewed test set;
   this is not a proof of population-wide zero errors. Existing correct maps and
   local corrections remain valid. Never sacrifice correctness for a percentage.
3. Measure canonical requests, cache reuse, local rematches, useful new mappings,
   eligible-work age, CPU/anonymous/cache memory and I/O. An unchanged-evidence
   replay must demonstrate avoided redundant work, not just renamed outcomes.
4. Exercise late canonical arrivals, changed source names/aliases, cache expiry,
   canonical outage/rate exhaustion, failure backoff and restart/resume. State
   bounds and first-attempt/provider fairness must hold under the measured load.
5. Full identity/first-seen comparison against the baseline; retain checkpoints,
   failures, quarantines, pre-v4 backups and valid accepted mappings. Record any
   explicitly justified removal separately; no silent resets or reassignment.
6. Verify ordinary discovery, exact-source large-series targets, local correction
   precedence, explicit partial providers, cache/outage and query/publication
   overlap with exact totals and last-good retention. Report fixture, copied
   state, live metadata and client evidence separately from media acceptance.

Use short bounded offline runs at 2 CPU/2 GiB. Recheck 4 CPU/4 GiB only if a new
change warrants comparison; prior work showed no clear gain. No full development
Mac crawl, live-state competing collector, daily episode recrawl, query scraping,
demand-refresh system, snapshot distribution or endurance/crash campaign.
Total storage remains 30,000,000,000 bytes including the 1 GB reserve.

For each work item, state implemented+verified, implemented+environment-blocked,
or not implemented with the precise blocker. A successful single-title query,
smaller queue or another percentage-only report is insufficient completion.

## Implementation result, October 14

The code, full copied-ledger gains, focused verification, scheduling/resource
measurements and rollout/rollback are now recorded in
[MAPPING_IMPLEMENTATION.md](MAPPING_IMPLEMENTATION.md). Implementation proceeded
past diagnosis. The prospective pre-labelled timing requirement was not met;
selection/splits froze first, metadata labels followed initial implementation.
This validation limitation is explicit alongside hosted/deployment blockers;
no complete mapping, freshness SLA or full-bootstrap capacity is claimed.
