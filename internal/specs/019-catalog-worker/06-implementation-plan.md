# Implementation sequence

Start from current main, preserve this handoff/unrelated work and refresh the
01 reuse matrix against main/PR #119. Do not merge its experimental migrations.
Contracts in 02/03/04/08/09 are selected engineering designs; implement/test
them rather than reopen every default. Report measured failures and adjust
routine bounds within their ranges. Changes to privacy, product behavior,
architecture, compatibility, cost or scope require maintainer decision.

## M0 — Baseline and source inventory

Record SHA, versions, existing tests and packaging baseline (C0). Inventory
provider/canonical fields and rights status. Use synthetic/permitted fixtures
while C7 is unresolved; private development does not authorize distribution.
Retain the historical PR memory observations as hypotheses, not benchmarks.

## M1 — Shared package and executable contracts

Implement core wheel with 09 records/DDL/identity encodings and 02 manifest
validation, golden vectors and synthetic fixture publisher. Keep separate uv
projects initially. Add cryptography only for Ed25519; use Python zstd and
existing HTTPX/AnyIO/SQLite. Verify installed wheels and packaging under C0/C1.
Extract only the AniWorld parsing/transport boundary actually needed, with
explicit config and no API startup side effects. Update env examples and agent
guidance as real settings/layout change. Do not describe proposed folders as
existing in current agent docs before this milestone.

## M2 — AniWorld worker and portable publisher

Private SQLite migrations, due-work leases/checkpoints, durable identity and
first_seen ledger, canonical mapping states, typed challenges and finite
budgets from 03. Export fresh allowlisted SQLite, sign and publish by 02.
Test C2, including large multi-slice titles, storage refusal and interrupted
publication. Portable Docker serves static files itself; no browser or hosted
query API. Mapping rights filter is implemented even in the private fixture
pipeline. Exit only after interrupted crawl resumes without lost identities.

## M3 — Consumer, durable jobs and first TV slice

Implement private-DB activation transaction and trust/recovery (C3), local
query interface, migration additions and frozen queued requests. Implement
job projection/blocked/retry/pause/restart service **before** routing real grabs
through the snapshot path. Wire one AniWorld canonical tvsearch and honest
unknown quality/size policy, then nonblocking scoped sampling. Keep official
default disabled. Run C4 and TV subset of C5 on controlled generated media.
No claim of provider playback from the fixture test. Exit: private producer →
artifact → consumer → real client's query/grab/import contract demonstrated,
with bad update and blocked job recovery.

## M4 — Complete routes, management and three providers

Implement RSS/offset/categories, movie/special/ID behavior, fallback, local
corrections and management auth/CAS/tasks. Add bounded targeted refresh after
ordinary consumption works. Adapt s.to and megakino with independent publication
and failure handling. Rehearse complete mainline upgrades (C6), feed/estimate
behavior (C5a), all clients and separately permitted real-provider paths (C5b).
Run full API/worker/core tests and supported platform images/packages. Update
Compose examples, user docs, env examples and internal agent guidance. Exit:
three-provider matrix and explicit evidence gaps; no hidden guesswork or data
loss. v3.0.0 functional release remains gated on its claimed integrations.

## M5 — Public rights, operations and default transition

C7 clearance and C8 deployment approval are independent gates. Compare measured
egress/host capacity; provision real source/domain/keys only with authorization.
Rehearse key compromise, rollback, backup and compatible-reader retention.
Only then ship official defaults and the staged mainline transition in 04.
Never merge a default pointing at an absent/unapproved endpoint. If required
fields cannot be distributed, bring a concrete alternative to the maintainer;
do not drop canonical capability or send queries to a hosted service silently.

Suggested review boundaries follow M1, M2, M3, M4 (split lifecycle/management
from extra adapters if needed), M5. Each must build/test independently. No
implementation, dependency edits, commits, pushes or deployments are part of
this specification review. Future implementation follows Conventional Commits
and the repository PR template, with gates linked to evidence artifacts.
