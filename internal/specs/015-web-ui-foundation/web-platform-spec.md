# AniBridge Web Platform Foundation Spec

Date: 2026-04-09
Status: Exploratory Draft
Scope: Web UI platform direction, product vision, frontend architecture,
supporting libraries, browser verification flows, notifications, metadata
strategy, CI/CD, Docker, and release implications

## 1. Purpose

This spec explores how AniBridge should add a Web UI after the repository
migration to the `apps/` layout.

The goal is not just to pick a frontend framework. The Web UI will affect:

- frontend architecture and runtime model
- operator workflows for browser-assisted challenge handling
- developer workflow and local development
- repository-level Node tooling
- API contracts and client generation
- metadata and discovery features
- notifications and alerting
- state persistence for browser sessions
- testing strategy
- CI/CD and release workflow
- Docker and deployment topology

This document is intentionally not final. It combines decisions, open questions,
tradeoffs, and idea dumps so AniBridge can iterate toward the right product
shape instead of prematurely locking itself into one architecture.

The decision process should optimize for:

- clean integration with the existing FastAPI backend
- high maintainability and explicit boundaries
- good TypeScript ergonomics
- fast local development
- predictable production builds
- low architectural duplication

## 2. Product Context

AniBridge already has a real backend and domain model. The Web UI is not the
origin point of the system; it is an additional control surface for an existing
service.

That matters because it changes the framework decision:

- AniBridge does not need a second backend framework.
- AniBridge does not need SEO-first page rendering.
- AniBridge does not benefit from splitting business logic across Python and
  another server runtime.
- AniBridge will benefit from a fast client app that consumes the FastAPI API
  cleanly and predictably.

This strongly biases the choice toward a client-first frontend architecture.

## 3. Expanded Product Vision

The Web UI should not be treated as a thin configuration dashboard only.

The broader vision now includes:

- an operator/admin UI
- a verification center for challenge-protected providers
- a live browser steering surface for manual intervention
- persistent browser sessions and cookie storage
- notifications when jobs require attention
- discovery and browsing surfaces for recent/trending content
- direct/manual download flows outside Sonarr/Prowlarr where appropriate

This changes the frontend conversation significantly. The Web UI is no longer
just "settings plus health"; it is becoming a true product surface.

## 4. Primary Recommendation

AniBridge should implement the Web UI as a React + TypeScript application in
`apps/web/` using Vite as the build tool and TanStack Router as the routing
layer.

Recommended foundation:

- Framework/runtime: React 19 + TypeScript
- Build tool: Vite
- Routing: TanStack Router
- Server-state/data fetching: TanStack Query
- API client generation: Orval from FastAPI OpenAPI
- Forms and validation: React Hook Form + Zod
- Styling: Tailwind CSS v4
- Headless UI primitives: Base UI or Radix UI
- App shell/component layer: local components plus selected shadcn/ui patterns
- Unit/component tests: Vitest + Testing Library
- Browser/E2E tests: Playwright
- API mocking for frontend dev/tests: MSW
- Optional component workshop: Storybook, phase 2

This should be managed with pnpm as the Node workspace tool once the Web UI is
introduced.

This is still the leading recommendation, but it is no longer the only model
under consideration because the product scope is wider than originally framed.

## 5. Why This Stack Fits AniBridge

## 5.1 Why React

React remains the safest default for an enterprise-grade admin or operator UI:

- large ecosystem
- mature TypeScript support
- broad hiring and community familiarity
- strong support from surrounding tooling

The decision is not based on hype. It is based on risk reduction and long-term
maintainability.

## 5.2 Why Vite

Vite is the best default fit for AniBridge because:

- the backend already exists
- the UI does not need a Node server as part of its default architecture
- it provides a fast local dev loop
- it produces a straightforward static build artifact
- it keeps the frontend runtime model simple

Vite also keeps the Web UI honest: build a frontend, not an accidental second
backend.

## 5.3 Why TanStack Router

TanStack Router fits AniBridge better than a minimal router because AniBridge is
likely to need:

- nested admin-style layouts
- typed route params
- typed search params for filters, pagination, and tabs
- route-driven data loading
- auth-aware route guards

That is exactly where TanStack Router is stronger than a barebones solution.

## 5.4 Why TanStack Query

AniBridge is API-driven. The frontend will be reading and mutating server state:

- jobs
- downloads
- mappings
- settings
- health/status
- search and queue actions

TanStack Query is a strong fit because it gives AniBridge:

- request caching
- background refetching
- mutation lifecycle handling
- invalidation
- optimistic UI where useful
- fewer custom loading and cache abstractions

## 5.5 Why generated API clients

AniBridge already exposes a backend contract through FastAPI/OpenAPI.

Do not hand-maintain fetch wrappers for every endpoint. Generate them.

Using Orval against the FastAPI OpenAPI schema gives:

- typed request/response models
- predictable frontend-backend alignment
- lower drift risk
- generated TanStack Query hooks if desired

This is one of the highest-leverage decisions in the whole frontend addition.

## 6. Radix UI vs Base UI

The earlier draft chose Radix UI as the default primitive layer. After further
research, that choice should be softened.

### What the official docs say

Base UI describes itself as a "comprehensive UI component library" for
accessible React interfaces, with fully open component APIs and a future-proof
foundation for professional interface design. It also explicitly documents CSP
handling and broader composability patterns.

Radix Primitives describes itself as a lower-level component library focused on
accessibility, customization, and developer experience, intended as a base
layer for design systems or for incremental adoption.

### Practical interpretation for AniBridge

Radix strengths:

- mature and widely battle-tested primitive layer
- excellent fit for incremental adoption
- strong ecosystem familiarity
- large amount of existing examples and community knowledge

Base UI strengths:

- broader and more modern "comprehensive but unstyled" component surface
- very flexible open APIs
- explicit attention to accessibility and CSP-related concerns
- designed by a team with direct Radix, Floating UI, and Material UI lineage

### Current recommendation

AniBridge should treat both as viable, with a slight architectural preference
toward Base UI for the new frontend exploration and a slight delivery-risk
preference toward Radix UI for the first implementation.

That means:

- if optimization target is lowest adoption risk right now: choose Radix UI
- if optimization target is long-term component flexibility and a more
  comprehensive unstyled base: choose Base UI

### Provisional decision

Do not lock this yet.

The next implementation spike should compare Base UI and Radix UI against three
real AniBridge surfaces:

- app shell/navigation
- verification queue/detail panel
- live browser session controls

Whichever library produces the cleaner result with less glue code should win.

## 7. TanStack Router vs TanStack Start

The earlier draft preferred TanStack Router directly. That still makes sense,
but TanStack Start deserves more explicit treatment.

### What the official docs say

TanStack Start describes itself as a full-stack framework powered by TanStack
Router and Vite. Its official docs say it adds SSR, streaming, server routes,
API routes, server functions, middleware, and full-stack bundling on top of
TanStack Router. The same docs also explicitly say that if you know you do not
need those capabilities, you may want to use TanStack Router alone.

The official docs also label TanStack Start as Release Candidate.

### Why Router-only is still the safer default

- AniBridge already has FastAPI as its backend
- adding Start introduces a second full-stack-capable runtime model
- the browser verification center and operator workflows do not inherently need
  frontend-owned server routes
- Router-only keeps deployment and local development simpler

### Why Start is still a serious candidate

Start becomes more attractive if AniBridge wants:

- same-origin auth middleware in the frontend layer
- server functions for frontend-owned orchestration glue
- hybrid rendering for a richer landing page or public app shell
- more integrated frontend hosting on platforms that like a JS app runtime

### Provisional decision

Treat TanStack Router + Vite as the default starting point.

Treat TanStack Start as the escalation path if the frontend begins to require:

- frontend-owned middleware
- frontend-owned BFF endpoints
- SSR/streaming
- more complex same-origin auth patterns

In other words:

- Start is not rejected
- Start is not the default
- Router-only wins unless clear full-stack frontend requirements emerge

## 8. Is Zustand Needed?

Not by default.

AniBridge should not add Zustand on day one just because many React apps do.

The frontend state categories should be separated first:

- server state: TanStack Query
- URL state: TanStack Router search params
- local component state: React state
- cross-session persisted UI preferences: optional client store

### When Zustand is not needed

Zustand is probably unnecessary for:

- API data
- paginated lists driven by URL/search params
- forms
- most modal/open-close state
- route-level filters that belong in the URL

### When Zustand may become useful

Zustand becomes attractive for cross-cutting client-only state such as:

- docked verification panel state
- browser viewer session UI state
- notification center preferences
- local operator workspace layout
- persisted non-URL UI preferences

### Provisional decision

Do not include Zustand in the initial bootstrap.

Revisit it only after at least one of these appears:

- multiple unrelated components need the same client-only state
- state persistence outside URL/search params becomes substantial
- the verification center creates a genuine control-plane store

If that happens, Zustand is a good candidate, but it is optional rather than
foundational.

## 9. Why Not Next.js As The Default

Next.js is not the recommended default for AniBridge.

Reasons:

- AniBridge already has a backend, so Next.js server features duplicate runtime
  concerns rather than solving a missing one.
- The first Web UI is much more likely to be an authenticated operator/admin UI
  than a marketing or SEO-heavy site.
- Next.js creates pressure to place API logic in two places: FastAPI and Next.
- The deployment model becomes more complex without clear product benefit.

Next.js should only be reconsidered if AniBridge later needs:

- SSR for a public-facing product site
- edge-rendered public pages
- server actions tightly coupled to the frontend runtime

That is not the current problem.

## 10. Alternatives Considered

## 6.1 Next.js

Pros:

- mature React meta-framework
- strong ecosystem
- SSR and hybrid rendering support
- excellent deployment story

Cons for AniBridge:

- adds a second server-capable runtime layer
- increases architecture complexity
- encourages logic duplication with FastAPI
- solves problems AniBridge does not currently have

Decision: not selected as the initial Web UI platform

## 6.2 React Router instead of TanStack Router

Pros:

- familiar
- widely adopted
- simpler mental model for small apps

Cons for AniBridge:

- weaker type-safety for route/search state
- less opinionated for the admin-style state AniBridge is likely to need

Decision: valid fallback, but not the recommended default

## 6.3 Vue or Svelte

Pros:

- good developer experience
- smaller conceptual surface in some areas

Cons for AniBridge:

- lower alignment with the maintainer's current likely ecosystem path
- weaker compatibility with the specific React-centric tooling stack proposed
- no clear repository-level advantage over React

Decision: not selected

## 11. Expanded Functional Scope

The Web UI scope should now be treated as at least four product areas, not one.

### 11.1 Operator console

- health and version
- queue/job visibility
- mapping and metadata inspection
- search/add flows
- settings and diagnostics

### 11.2 Verification center

- jobs blocked by provider challenge
- challenge reason and provider visibility
- explicit human-in-the-loop workflows
- audit trail and retry/resume flows

### 11.3 Live browser steering

- attach to a persistent browser session
- manually solve Cloudflare Turnstile or similar challenges
- steer navigation live
- preserve cookies and session state
- return control to AniBridge after manual verification

### 11.4 Discovery and manual media operations

- trending/recent content landing view
- provider-backed availability browsing
- manual download triggers
- optional direct ZIP or single-episode manual download flows

## 12. Expected Web UI Scope

The first Web UI should not try to mirror every backend capability. It should
ship a strong operational core first.

Phase 1 capabilities:

- authentication/bootstrap if required
- health and version view
- dashboard overview that is actually informative, not a blank shell
- active jobs/download queue
- mappings browser/editor
- search and add flow
- settings/config inspection where safe
- error and background task visibility
- verification queue and detail view

Phase 2 capabilities:

- richer tables and filtering
- bulk actions
- audit/history views
- improved onboarding and diagnostics
- more polished component system and Storybook coverage
- notification rules and delivery configuration
- live browser steering
- discovery/trending surfaces
- manual/direct download actions

Non-goal for phase 1:

- replacing all docs with UI
- public marketing site behavior
- duplicating backend business rules in the browser

## 13. Verification Center And Browser Session Architecture

This is likely one of the most differentiating AniBridge features and needs to
be designed as a first-class subsystem.

## 13.1 Problem

Some providers can fail behind Cloudflare Turnstile or similar protection,
especially for redirect flows. AniBridge needs a human-assisted fallback that is
operationally clean instead of opaque and brittle.

## 13.2 Required capabilities

- detect challenge-blocked jobs in the backend
- pause and persist affected flows
- expose blocked jobs to the frontend
- attach an operator to a live browser session
- preserve cookies/profile/session data across attempts
- resume backend work after successful intervention

## 13.3 Architecture options

### Option A: dedicated persistent browser container plus noVNC

Model:

- one or more Chromium containers
- persistent user-data-dir mounted on a volume
- X server plus noVNC for remote operator interaction
- AniBridge backend coordinates sessions and job assignment

Pros:

- simple conceptual model
- visible browser is real, not simulated
- proven remote desktop pattern

Cons:

- noVNC is not a great UX on mobile
- remote desktop UX is coarse
- less app-native feeling

### Option B: Playwright-driven browser service plus custom live viewer

Model:

- persistent Playwright/Chromium sessions
- backend/browser-service exposes screenshots, DOM metadata, and control
  endpoints or a websocket stream
- frontend renders a custom control panel instead of a full remote desktop

Pros:

- more integrated product experience
- more controllable and auditable
- potentially better responsive/mobile UX

Cons:

- much more engineering effort
- trickier to make robust for arbitrary anti-bot flows

### Option C: hybrid model

Model:

- start with noVNC for operator steering
- later add a richer AniBridge-native control surface for common actions

Pros:

- pragmatic
- faster to ship
- lets AniBridge learn before overbuilding

Cons:

- transitional architecture
- UX inconsistency between early and later flows

### Provisional direction

The most realistic starting point is Option C:

- phase 1: dedicated browser resolver container + persistent profile + noVNC
- phase 2: more app-native browser session tooling where it clearly pays off

## 13.4 Persistence requirements

Browser verification must be stateful.

AniBridge should persist:

- browser profile directory on disk/volume
- session ownership metadata
- job-to-session mapping
- verification audit events
- cookie/session freshness signals where feasible

The browser should not be disposable for every verification event unless a
provider explicitly requires it.

## 14. Notifications And Alerting

AniBridge should likely gain an alerting subsystem once the verification center
exists.

Candidate notification targets:

- Discord webhook
- generic webhook
- email
- SMS later if there is a real need

Candidate events:

- challenge required
- repeated provider failure
- browser session expired
- download job stuck
- metadata sync failure

Recommendation:

- start with generic webhook plus Discord webhook
- add email after core notification abstractions exist

Backend implications:

- notification settings model
- delivery retry handling
- event classification and deduplication
- audit log for outbound notifications

## 15. Landing Page / Discovery Surface

The start page after login should not be blank or just settings-oriented.

It should become a useful operational and discovery surface.

Candidate widgets:

- current queue state
- recent failures needing attention
- latest successful downloads
- trending anime
- trending series
- trending movies
- provider/system health summary

## 15.1 Candidate metadata/trending sources

Potential external metadata sources:

- TMDb for trending movies and TV
- AniList for anime discovery and seasonal/trending anime
- TVDB as a canonical metadata/mapping source if licensing and integration fit
- Trakt as an optional discovery/trending source later

What the current docs indicate:

- TMDb exposes trending movie and TV endpoints
- AniList exposes a large GraphQL API but also documents rate limiting and terms
  of use constraints, including restrictions on large-scale data collection

### Provisional recommendation

For the landing page:

- use TMDb for trending movies and TV
- evaluate AniList for anime discovery carefully, with terms/rate limits in mind
- do not build a large background metadata mirror until the product really needs
  it

## 15.2 Only show items AniBridge can actually serve?

This is a major product question.

Possible approaches:

### Approach A: show global trending content regardless of current provider availability

Pros:

- easiest to implement
- best discovery UX

Cons:

- may frustrate users if many entries are not actually available

### Approach B: show only provider-confirmed available items

Pros:

- operationally honest
- stronger trust in the UI

Cons:

- requires large provider crawling/indexing work
- implies substantial backend refactor and scheduled sync jobs
- requires metadata normalization and provider-to-canonical mapping

### Approach C: mixed model

- show global trending content
- annotate whether AniBridge currently knows it as available, unknown, or
  unavailable

This is the strongest candidate right now because it avoids building a full
catalog ingestion platform too early while still being honest about certainty.

## 16. Manual And Direct Download Flows

The frontend may eventually support direct/manual download workflows outside the
Arr stack.

Potential capabilities:

- trigger a direct episode download
- download a season or show as a ZIP archive
- download to a user-selected path inside the container/runtime
- queue a manual background download job without Sonarr/Prowlarr

These are useful but potentially high-risk because they expand AniBridge from an
automation bridge into a more direct media operations tool.

Open questions:

- Should these flows be admin-only?
- Should they reuse the same queue/job model as Arr-driven jobs?
- Should ZIP generation happen synchronously, asynchronously, or not at all?
- How should path selection be sandboxed to avoid unsafe filesystem writes?

Recommendation:

- keep manual direct download flows in the vision
- do not put them in the first implementation slice

## 17. Recommended Frontend Libraries

## 8.1 Core runtime

- `react`
- `react-dom`
- `typescript`
- `vite`
- `@vitejs/plugin-react-swc`

Rationale:

- React + TypeScript is the baseline
- SWC keeps Vite builds fast

## 8.2 Routing and server state

- `@tanstack/react-router`
- `@tanstack/react-query`
- `@tanstack/react-query-devtools`

Rationale:

- typed routes and search params
- strong async server-state model
- better maintainability than ad hoc caching/fetch wrappers

## 8.3 API contract and validation

- `orval`
- `zod`

Rationale:

- OpenAPI-driven frontend client generation
- runtime validation at boundaries

Note:

- If Orval-generated hooks become too opinionated, AniBridge can generate raw
  clients only and keep query composition local.

## 8.4 Forms

- `react-hook-form`
- `@hookform/resolvers`

Rationale:

- ergonomic forms
- strong integration with Zod

## 17.5 UI foundation

- `tailwindcss`
- `@base-ui/react` or `@radix-ui/react-*`
- `lucide-react`

Rationale:

- Tailwind gives fast composition and token-based scaling
- Base UI or Radix provides accessible primitives without forcing a full design
  system
- Lucide is a good default icon set

Optional:

- selected shadcn/ui components as a source pattern, not as a dependency-first
  design strategy

Rule:

- keep components in `apps/web/src/components` until true cross-app reuse
  exists; do not create `packages/ui` on day one

## 8.6 Tables and visualization

- `@tanstack/react-table` when complex data grids appear
- charting library deferred until a real dashboard need exists

Recommendation:

- do not pick a charting library until concrete UI requirements exist

## 8.7 Testing and mocking

- `vitest`
- `@testing-library/react`
- `@testing-library/user-event`
- `playwright`
- `msw`

Rationale:

- Vitest matches the Vite stack cleanly
- Playwright is the best fit for browser-level confidence
- MSW keeps API mocking aligned across development and tests

## 8.8 Optional phase-2 tooling

- `storybook`

Use Storybook only when:

- the component surface becomes large enough
- UI collaboration benefits from isolated component documentation
- design-system consistency becomes a real problem

Do not add Storybook in the first bootstrap commit unless the UI scope is
already broad.

## 18. Backend Expansion Required

The Web UI vision implies a non-trivial backend expansion.

The backend will likely need new API groups for:

- dashboard overview
- queue and job detail
- verification sessions
- browser resolver lifecycle
- notifications
- discovery/trending content aggregation
- manual download operations

The backend may also need domain refactoring for:

- explicit job state machine
- provider challenge states
- session ownership and persistence
- richer audit events
- canonical content and provider availability mapping

## 19. Repository Changes Required

## 9.1 Add Node workspace at repo root

When `apps/web/` becomes real, AniBridge should introduce:

- root `package.json`
- root `pnpm-workspace.yaml`

Workspace members should initially be:

- `docs`
- `apps/web`

The Python backend remains managed by `uv`.

This is a mixed-language monorepo:

- `uv` for Python
- `pnpm` for Node

Do not try to force one package manager to own both ecosystems.

## 9.2 Proposed target structure after frontend bootstrap

```text
/
  apps/
    api/
    web/
  docs/
  internal/
    agents/
    specs/
  docker/
  scripts/
  package.json
  pnpm-workspace.yaml
```

## 9.3 No shared packages on day one

Do not create these immediately:

- `packages/ui`
- `packages/config`
- `packages/types`

Create shared packages only after real duplication appears.

Early extraction often creates more churn than clarity.

## 20. API Integration Strategy

AniBridge should treat the FastAPI OpenAPI schema as the contract source for the
Web UI.

Recommended approach:

1. Expose stable OpenAPI output from the backend
2. Generate frontend API clients from it
3. Keep generated code in a clearly marked location inside `apps/web`
4. Wrap generated primitives with feature-focused query/mutation hooks only when
   needed

Suggested layout:

```text
apps/web/
  src/
    api/
      generated/
      client/
    features/
      jobs/
      mappings/
      settings/
```

Rule:

- the backend owns schemas
- the frontend consumes them
- contract drift should be caught in CI

## 21. Local Development Model

AniBridge should support this development flow:

- backend running via `cd apps/api && uv run python -m app.main`
- frontend running via `cd apps/web && pnpm dev`
- docs running independently via `pnpm --prefix docs dev`

The frontend should call the backend through one of:

- Vite dev proxy to FastAPI
- explicit environment variable for API base URL

Recommendation:

- use a Vite dev proxy for the common local path to avoid CORS friction
- still support an explicit API base URL env var for advanced setups

Additional local-dev mode to support later:

- API running locally
- browser-resolver container running via Docker
- optional noVNC/browser viewer attached
- frontend running locally

This mixed local-dev mode is probably the most realistic verification workflow.

## 22. Configuration Requirements

The Web UI will need its own environment model.

Expected variables:

- public API base URL
- app environment name
- optional Sentry/telemetry DSN later
- optional feature flags later

Policy:

- add `apps/web/.env.example` when the app is bootstrapped
- document frontend env vars in docs
- keep backend env changes reflected in `apps/api/.env.example`

## 23. CI/CD Implications

The Web UI should expand CI in a path-aware way.

## 13.1 New CI jobs to add

- frontend install
- frontend lint
- frontend typecheck
- frontend unit/component tests
- frontend production build
- frontend E2E tests
- API client generation drift check

## 13.2 Path triggers

Web UI jobs should run on changes to:

- `apps/web/**`
- root Node workspace files
- API contract sources when generated clients are affected

Examples:

- `apps/api/app/**` if OpenAPI changes can affect generated clients
- `apps/api/pyproject.toml` only if API generation depends on backend runtime

## 13.3 CI shape recommendation

Minimum frontend workflow:

- `pnpm install --frozen-lockfile`
- `pnpm --filter ./apps/web lint`
- `pnpm --filter ./apps/web typecheck`
- `pnpm --filter ./apps/web test`
- `pnpm --filter ./apps/web build`

Later:

- Playwright job with browser install and trace artifact upload

## 13.4 Contract drift gate

Add a CI check that fails if:

- OpenAPI-derived client output is stale

This prevents backend/frontend mismatch from creeping in silently.

## 24. Docker And Deployment Implications

AniBridge should not overcomplicate frontend delivery in the first iteration.

## 24.1 Development Docker

Add a frontend service to development compose only when the Web UI exists.

Suggested future service model:

- `web-dev` runs the Vite dev server
- proxies API calls to `api`
- can be enabled only in dev-oriented compose files

AniBridge will also likely need a browser-resolver service in dev and possibly
production.

Potential future compose services:

- `api`
- `web`
- `browser-resolver`
- `novnc` or equivalent viewer

## 24.2 Browser resolver deployment options

### Option A: bundled inside the API container

Not recommended.

This mixes browser runtime concerns into the Python API image and makes scaling,
debugging, and sandboxing worse.

### Option B: dedicated browser-resolver container

Recommended default.

This keeps browser automation isolated and lets AniBridge mount persistent
browser profile storage explicitly.

### Option C: external managed browser service

Possible later, but not the default.

This adds dependency and cost concerns that are probably premature.

## 24.3 Production deployment options

Two viable models exist.

### Option A: static deployment for the Web UI

- build `apps/web`
- serve static assets from a CDN, object store, or edge platform
- keep FastAPI as the API origin

Pros:

- simple
- cheap
- matches the Vite architecture

Cons:

- requires explicit API origin strategy

### Option B: serve built assets through a reverse proxy/container

- build static frontend
- ship it with nginx/caddy or another web server
- proxy `/api` to FastAPI

Pros:

- easy single-origin setup
- straightforward container deployment

Cons:

- one more deployment artifact to own

Recommendation:

- start with static deployment or reverse-proxy static hosting
- do not introduce a frontend SSR server by default

## 24.4 Dockerfile strategy

Do not merge the frontend into the Python image.

Preferred future approach:

- separate Dockerfile for `apps/web` if containerized
- separate release artifact from `apps/api`

This keeps runtime responsibilities explicit.

## 25. Release And Versioning Implications

AniBridge needs to decide whether the Web UI version is:

- coupled to the backend release version, or
- versioned independently

Recommendation:

- keep a single repo release version initially
- ship backend and frontend together until their cadence diverges

Why:

- simpler release communication
- simpler changelog story
- fewer moving parts in early adoption

If the Web UI later becomes independently deployable at a different cadence,
revisit this.

## 26. Testing Strategy

AniBridge should test the Web UI at three levels.

## 16.1 Unit/component tests

Use Vitest + Testing Library for:

- components
- hooks
- feature modules
- form behavior

## 16.2 Browser/E2E tests

Use Playwright for:

- login/bootstrap flow if applicable
- navigation and route guards
- core operational workflows
- error-state and loading-state coverage

## 16.3 API mocking

Use MSW for:

- local UI development against incomplete backend features
- component and integration tests
- deterministic frontend test behavior

## 27. Design-System Guidance

The first Web UI should not try to become a giant abstract design system.

Recommended approach:

- define a small token set early
- standardize layout, spacing, typography, and state patterns
- keep most components local to `apps/web`
- extract shared UI only when a second app or true cross-surface reuse appears

This preserves speed while still giving the frontend a clean internal structure.

## 28. Security And Auth Considerations

The Web UI decision affects auth and deployment.

The frontend should assume:

- authenticated operations will exist or may exist later
- browser calls must respect backend auth/session design
- no business-critical authorization logic should live only in the frontend

Required follow-up once the UI starts:

- define auth model
- define CSRF/session/token expectations
- define cross-origin or same-origin deployment strategy
- define verification session permissions
- define notification configuration permissions
- define safe path restrictions for manual download targets

## 29. Suggested Implementation Tracks

The work is now too broad for a single linear sequence. AniBridge should likely
split the future work into tracks.

### Track A: frontend foundation

- root pnpm workspace
- `apps/web` bootstrap
- routing, query, forms, styling
- app shell and auth/bootstrap

### Track B: API platform expansion

- dashboard endpoints
- verification session endpoints
- notification endpoints
- manual download endpoints

### Track C: browser resolver subsystem

- persistent browser container
- session lifecycle
- storage model
- noVNC or equivalent viewer

### Track D: metadata/discovery

- trending/recent source integration
- canonical ID strategy
- availability annotations

## 30. Recommended Implementation Sequence

1. Approve this platform decision
2. Add root Node workspace (`package.json`, `pnpm-workspace.yaml`)
3. Bootstrap `apps/web` with React + TypeScript + Vite
4. Add Tailwind CSS, TanStack Router, TanStack Query
5. Add Vitest and Playwright scaffolding
6. Wire OpenAPI client generation from FastAPI
7. Build one vertical slice:
   - health/version page
   - dashboard shell
   - one jobs or mappings page
8. Expand CI to include frontend jobs
9. Add frontend Docker/deployment path as needed

## 31. Explicit Decisions

### Adopt now

- `apps/web` as the Web UI location
- React + TypeScript + Vite
- TanStack Router as the default starting point
- TanStack Query
- pnpm for Node workspace management
- generated API client from OpenAPI
- Vitest + Playwright + MSW

### Keep open for near-term evaluation

- Base UI vs Radix UI
- TanStack Router vs TanStack Start
- whether Zustand is needed after the verification center takes shape
- how the live browser viewer is delivered
- whether landing discovery data should be global or provider-aware

### Defer until concrete need exists

- Storybook
- charting library
- shared `packages/*`
- SSR/full-stack frontend framework adoption
- frontend independent versioning

## 32. Final Recommendation For The Current Moment

AniBridge should build its first Web UI as a Vite-powered React application in
`apps/web`, backed initially by TanStack Router, TanStack Query, and an
OpenAPI-generated client.

However, the product scope should now be understood as much larger than a basic
dashboard. The Web UI should be planned as an operator platform that can grow
toward:

- challenge/verification workflows
- live browser steering
- notifications
- discovery surfaces
- manual media operations

So the right next move is not "finalize every library forever". The right next
move is:

- lock the initial bootstrap direction
- identify which decisions require implementation spikes
- keep the larger product/system vision explicit

This remains the cleanest architecture for the current product because it:

- respects the existing FastAPI backend
- avoids duplicating server responsibilities
- gives strong TypeScript ergonomics
- scales well for an admin/operator interface
- keeps deployment and local development simpler than a full-stack React
  meta-framework

If the frontend later proves it needs server functions, middleware, SSR, or a
frontend-owned BFF layer, AniBridge should revisit TanStack Start explicitly
instead of drifting into it accidentally.

## 33. References

- Vite getting started: https://vite.dev/guide/
- Vite SSR guide: https://vite.dev/guide/ssr.html
- TanStack Router overview: https://tanstack.com/router/learn/docs/framework/react/overview
- TanStack Router search params guide: https://tanstack.com/router/latest/docs/guide/search-params
- TanStack Query docs: https://tanstack.com/query/latest/docs/react/
- TanStack Start overview: https://tanstack.com/start/latest/docs/framework/react/overview
- TanStack Start comparison: https://tanstack.com/start/latest/docs/framework/react/comparison
- Orval React Query generation: https://orval.dev/docs/guides/react-query
- Base UI overview: https://base-ui.com/react/overview/about
- Base UI accessibility: https://base-ui.com/react/overview/accessibility
- Base UI CSP provider: https://base-ui.com/react/utils/csp-provider
- Radix Primitives intro: https://www.radix-ui.com/primitives/docs/overview/introduction
- Zustand introduction: https://zustand.docs.pmnd.rs/getting-started/introduction
- Vitest docs: https://main.vitest.dev/
- Playwright docs: https://playwright.dev/
- MSW docs: https://mswjs.io/
- Storybook docs: https://storybook.js.org/docs
- TMDb trending movies: https://developer.themoviedb.org/reference/trending-movies
- TMDb trending TV: https://developer.themoviedb.org/reference/trending-tv
- AniList API docs: https://anilist.gitbook.io/anilist-apiv2-docs
- AniList terms of use: https://anilist.gitbook.io/anilist-apiv2-docs/docs/guide/terms-of-use
- AniList rate limiting: https://anilist.gitbook.io/anilist-apiv2-docs/docs/guide/rate-limiting
