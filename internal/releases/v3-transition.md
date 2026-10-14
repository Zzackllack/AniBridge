# v3 integration and default-branch transition

Status: ongoing development and private-server testing. This is an integration
plan, not a release declaration or permission to redeploy the pilot.

## Branch policy now

- `main` remains the default branch and stable v2 release source.
- `v3` was created from current `main`, `e14a041c0a8ddeac71aab7b8f564ac4a9584603a`
  (`v2.6.0`). It has a dedicated active ruleset targeting `refs/heads/v3`.
- `zzackllack-aux/catalog-query-api-implementation` is submitted as a draft PR
  into `v3`. The catalog implementation, preview workflow and this checklist are
  reviewed together; no workflow-only commit was applied directly to `v3`.
- Subsequent features/fixes should use focused PRs into `v3`. Bring relevant
  stable fixes forward from `main` periodically, resolving differences explicitly.
- Older worker/snapshot/evaluation branches are historical references, not a
  merge queue. The selected request API contract supersedes client snapshot
  distribution; do not merge abandoned distribution machinery back in.
- Merging the draft into `v3`, changing the default branch, publishing a release
  and redeploying Coolify are separate maintainer decisions.

The initial `V3 integration` ruleset mirrors the current `Main-Prot` review,
required-status, CodeQL and bypass configuration with an explicit `v3` target.
It is a starting policy, not proof that every desired CI check is enforced.
In particular, the inherited required status is the conventional PR title check;
unit tests and build checks still need deliberate enforcement below.

## Preview containers for Coolify

Workflow: [Preview / Container Images](../../.github/workflows/preview-images.yml).
It builds the existing API and worker Dockerfiles for `linux/amd64` and
`linux/arm64` on native GitHub runners. The source is the actual PR head commit,
not GitHub's synthetic merge commit. Each architecture must build and import its
installed application modules with network access disabled before a combined
manifest is tagged. Provenance/SBOM metadata accompanies the images.

| Component | GHCR package | Deployment use |
| --- | --- | --- |
| API | `ghcr.io/zzackllack/anibridge-api-preview` | Disposable local AniBridge client |
| Catalog worker | `ghcr.io/zzackllack/anibridge-catalog-worker-preview` | Initializer, collector and metadata read service |

Triggers, when container inputs change:

- Same-repository PRs into `v3`, including drafts: moving `pr-N` tag.
- Pushes to `v3`: moving `v3` tag, once this workflow has been integrated there.
- Pushes to `preview/**`: a Docker-normalized branch tag. A preview branch must
  contain the workflow and catalog Dockerfiles, so create it from this work or
  the integrated `v3`, not the original v2 commit.
- Every run also publishes `sha-<full-40-character-source-commit>`.
- Fork PRs and Dependabot events do not receive registry publication jobs. There
  is no `pull_request_target` checkout/build and no deployment trigger.

Separate package names prevent this workflow from replacing stable `latest`,
`main`, `edge` or version tags. A source tag identifies code, but a rebuild can
resolve a newer base image; **pin the manifest digest for an immutable deployment
and rollback**. The workflow summary prints the tags, source commit and manifest
information. A successful image build/import is not a substitute for full tests,
server acceptance or a release gate. A draft PR is not production-ready software.

Example inspection after a successful run:

```sh
REPAIR_COMMIT=$(git rev-parse HEAD)
API_PREVIEW="ghcr.io/zzackllack/anibridge-api-preview:sha-$REPAIR_COMMIT"
WORKER_PREVIEW="ghcr.io/zzackllack/anibridge-catalog-worker-preview:sha-$REPAIR_COMMIT"
docker buildx imagetools inspect "$API_PREVIEW"
docker buildx imagetools inspect "$WORKER_PREVIEW"
# Copy each printed sha256 manifest digest into the reviewed deployment plan.
```

New GHCR packages may initially be private. Confirm package visibility and
repository access after first publication. For private packages, configure
Coolify registry authentication with an operator-owned credential limited to
`read:packages`; the ephemeral workflow `GITHUB_TOKEN` is not a server credential.
Public visibility is a separate package-setting decision, not something this
workflow silently changes. Do not put registry credentials in compose or Git.

For the existing pilot, replace all three worker image references together and
set the initializer/collector/metadata image to the **same worker digest**. Pulling
registry images requires replacing the old local-image `pull_policy: never`
setting deliberately; preserve every other service setting. Retain the prior
local image and original compose for rollback. Update the disposable client to
its matching API digest separately. Do not deploy the worker image as the API.

The existing [local-image staging helper](../../scripts/catalog/query_pilot/stage_upgrade.py)
only accepts the previous local worker image naming convention. Do not feed it
registry refs or broaden its guard accidentally. A registry cutover needs its own
reviewed image/pull-policy patch against the then-current Coolify source, preserving
volumes, config, identities, checkpoints, retry deadlines and pre-v4 backups.
Use the [server guide](../../scripts/catalog/query_pilot/SERVER.md) for backup,
publication, validation and rollback sequencing. No preview workflow restarts the
collector, changes resource limits or routes, or schedules a bootstrap.

## Required before changing the default branch

Each item needs concrete evidence and an owner decision. Do not mark an item
complete because the draft exists or one image build succeeds.

### 1. Branch protection and review

- [ ] Decide the long-term model: keep `main` as the active branch and integrate
  v3 when ready, or make `v3` the developer default while retaining explicit v2
  release support. A major version does not require a default-branch rename.
- [ ] Protect stable `main` by explicit name before any default switch. Current
  `Main-Prot` and Copilot rules target `~DEFAULT_BRANCH` and would follow the switch.
- [ ] Review and retain explicit `v3` protection, CodeQL coverage, CODEOWNERS,
  required approvals, conversation resolution and bypass actors. Check that the
  release deploy key can bypass only the intended release branch rules.
- [ ] Require meaningful CI status checks, not only `Conventional Commit Title`.
  Verify an intentionally failing test/build blocks a normal merge.
- [ ] Confirm review behavior for drafts and later ready-for-review transitions;
  current Copilot settings exclude drafts and do not review every push.

### 2. CI coverage and reproducibility

- [ ] Add independent API, `packages/catalog-core` and `apps/catalog-worker` jobs
  with their own frozen uv projects. Local October 14 YAML implements these jobs; hosted execution remains unverified.
- [ ] Verify the October 14 unconditional worker/core/workflow coverage and an
  always-running final gate so skipped path-filter workflows do not leave a
  required check pending forever. Verify PRs into both supported base branches.
- [ ] Add API/worker package and image smoke builds to the required gate; include
  the supported architectures and actual installed wheel imports.
- [ ] Run isolated contract/migration/backup/restore tests and bounded offline
  integration checks. Keep provider-network and media acquisition tests opt-in.
- [x] Replace Ruff's auto-commit/rebase/force-with-lease workflow with check-only
  validation or a separately invoked fix workflow. A validation job should not
  move a contributor's branch while review/builds are running.
- [ ] Audit `workflow_run`, scheduled, manual and target events for default-branch
  dependence. Keep privileged follow-up jobs from executing untrusted artifacts.
- [ ] Verify action versions, least permissions, fork behavior, required-check
  names, concurrency and preview artifact/registry retention policy.

### 3. Release branch and version policy

- [ ] Choose explicit stable and prerelease sources independently of GitHub's
  default branch. `cut-release.yml` currently allows real releases only from
  `github.event.repository.default_branch`.
- [ ] Update `Makefile`'s `RELEASE_REF ?= main`, branch-policy documentation and
  release-tag guard text together. Rehearse successful and rejected selections.
- [ ] Define v3 compatibility and migrations, including supported v2 upgrades,
  forward restoration and any breaking config/API/deployment contracts.
- [ ] Add a genuine prerelease path (`3.0.0-alpha.N`, beta, RC): supported version
  parsing, GitHub prerelease status, notes, artifacts and distinct image tags.
  Current release creation accepts only patch/minor/major and publishes `latest`.
- [ ] Ensure v3 prereleases never overwrite stable `latest` or stable major tags.
  Build/promote the tested commit/digest; retain preflight's moving-tip guard.
- [ ] Rehearse dry runs, release deployment-key access, atomic commit/tag pushes,
  failure handling and asset generation without publishing an unintended release.
- [ ] Decide v2 maintenance ownership, version source and support duration. If
  needed, create `release/2.x` at the selected stable tip and configure its own
  releases before v3 replaces the active stable line.

### 4. Continuous image publishing and deployment

- [ ] Remove the policy mismatch in `publish.yml`: push filtering is hardcoded to
  `main`, while `edge` and an additional `main` tag follow the default branch.
- [ ] Define stable, preview and release image naming and supported architectures
  for both API and worker. Avoid a version/default switch changing tag meaning.
- [ ] Verify preview GHCR permissions/visibility, native architecture manifests,
  digest pinning, cleanup retention and rollback availability in Coolify.
- [ ] Decide which default/stable refs may publish automatically and which need
  an explicit release/deployment approval. Keep package publication separate from
  server rollout; prevent an image tag update from silently upgrading the pilot.
- [ ] Complete the existing pilot upgrade with retained state and classify CQ-22
  maintenance diagnostics. The current local repairs are ahead of the deployed
  worker, so a successful CI build does not mean the server has them.
- [ ] Verify NetBird and Docker network ranges, backups, source/token mounts,
  storage reserve, retries/first-seen and resource profiles at cutover. No reset
  of failures or full bootstrap is an upgrade strategy.

### 5. Integrations and product readiness

- [ ] Check Cloudflare's actual production branch, preview deployments, secrets
  and domain routing. `wrangler.toml` alone does not establish dashboard settings.
- [ ] Set Dependabot targets for the supported lines and add worker/core projects
  where appropriate; the present config defaults to the default branch.
- [ ] Audit code-scanning, dependency/security tools, badges, raw-file links,
  contributing instructions, release automation and external webhooks for `main`
  or default-branch assumptions.
- [ ] Close or explicitly accept catalog coverage, mapping, freshness, maintenance,
  migration and capacity gaps using the [issue ledger](../specs/020-catalog-query-api-evaluation/ISSUES.md).
  Keep fixtures, live metadata, generated acquisition, live extraction, import
  and playback as distinct evidence; a short run is not an endurance/SLA proof.
- [ ] Approve the public-facing product policy: opt-in versus default catalog,
  service ownership/privacy/authentication, supported providers, quality profiles,
  migration guide and operational support. A private pilot is not a hosted default.

## Execution and rollback for a later default change

1. Record exact stable/integration tips, active rulesets, required-check names,
   release refs, image channels and external integration settings.
2. Land and verify the policy fixes above while `main` is still default. Bootstrap
   any default-only workflow deliberately; do not assume a new branch's scheduled
   or manual workflow is active simply because its YAML exists.
3. Rehearse the supported stable and prerelease paths, plus their rejection paths.
4. Obtain the maintainer's explicit decision for the selected default and release
   model. Make the repository setting change only after the evidence is reviewed.
5. Open a test PR, inspect rules/checks, verify manual and scheduled workflows,
   dependency updates and docs previews, and confirm stable tags were untouched.
6. If behavior differs, restore the previous default and recorded integration
   settings. Keep `main` explicitly protected throughout. Reverting the setting
   does not undo published images/releases, hence the prior publication guards.

## References

- [GitHub default branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-branches-in-your-repository/changing-the-default-branch)
- [GitHub workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [Docker multi-platform builds](https://docs.docker.com/build/ci/github-actions/multi-platform/)
- [Container registry authentication](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Current release/CI agent guide](../agents/release-ci.md)

## October 14 local implementation update

`tests.yml` now includes independent frozen API/core/worker jobs, installed-wheel
smokes and an unconditional final gate for PRs into both `main` and `v3`. These
changes are local and unpushed; hosted checks, native AMD64/ARM64 image gates and
protection enforcement remain open. No default-branch, protection, release or
publication policy was changed. See spec 020's mapping implementation evidence
for the separately tested parser, correspondence and scheduling changes.
