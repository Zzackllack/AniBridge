# AniBridge Web Platform Foundation Spec

Date: 2026-04-09
Status: Proposed
Scope: Web UI platform decision, frontend architecture, supporting libraries,
tooling, CI/CD, Docker, and release implications

## 1. Purpose

This spec defines how AniBridge should add a Web UI after the repository
migration to the `apps/` layout.

The goal is not just to pick a frontend framework. The Web UI will affect:

- frontend architecture and runtime model
- developer workflow and local development
- repository-level Node tooling
- API contracts and client generation
- testing strategy
- CI/CD and release workflow
- Docker and deployment topology

The decision should optimize for:

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

## 3. Primary Recommendation

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
- Headless UI primitives: Radix UI
- App shell/component layer: local components plus selected shadcn/ui patterns
- Unit/component tests: Vitest + Testing Library
- Browser/E2E tests: Playwright
- API mocking for frontend dev/tests: MSW
- Optional component workshop: Storybook, phase 2

This should be managed with pnpm as the Node workspace tool once the Web UI is
introduced.

## 4. Why This Stack Fits AniBridge

## 4.1 Why React

React remains the safest default for an enterprise-grade admin or operator UI:

- large ecosystem
- mature TypeScript support
- broad hiring and community familiarity
- strong support from surrounding tooling

The decision is not based on hype. It is based on risk reduction and long-term
maintainability.

## 4.2 Why Vite

Vite is the best default fit for AniBridge because:

- the backend already exists
- the UI does not need a Node server as part of its default architecture
- it provides a fast local dev loop
- it produces a straightforward static build artifact
- it keeps the frontend runtime model simple

Vite also keeps the Web UI honest: build a frontend, not an accidental second
backend.

## 4.3 Why TanStack Router

TanStack Router fits AniBridge better than a minimal router because AniBridge is
likely to need:

- nested admin-style layouts
- typed route params
- typed search params for filters, pagination, and tabs
- route-driven data loading
- auth-aware route guards

That is exactly where TanStack Router is stronger than a barebones solution.

## 4.4 Why TanStack Query

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

## 4.5 Why generated API clients

AniBridge already exposes a backend contract through FastAPI/OpenAPI.

Do not hand-maintain fetch wrappers for every endpoint. Generate them.

Using Orval against the FastAPI OpenAPI schema gives:

- typed request/response models
- predictable frontend-backend alignment
- lower drift risk
- generated TanStack Query hooks if desired

This is one of the highest-leverage decisions in the whole frontend addition.

## 5. Why Not Next.js As The Default

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

## 6. Alternatives Considered

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

## 7. Expected Web UI Scope

The first Web UI should not try to mirror every backend capability. It should
ship a strong operational core first.

Phase 1 capabilities:

- authentication/bootstrap if required
- health and version view
- dashboard overview
- active jobs/download queue
- mappings browser/editor
- search and add flow
- settings/config inspection where safe
- error and background task visibility

Phase 2 capabilities:

- richer tables and filtering
- bulk actions
- audit/history views
- improved onboarding and diagnostics
- more polished component system and Storybook coverage

Non-goal for phase 1:

- replacing all docs with UI
- public marketing site behavior
- duplicating backend business rules in the browser

## 8. Recommended Frontend Libraries

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

## 8.5 UI foundation

- `tailwindcss`
- `@radix-ui/react-*` primitives as needed
- `lucide-react`

Rationale:

- Tailwind gives fast composition and token-based scaling
- Radix provides accessible primitives without forcing a full design system
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

## 9. Repository Changes Required

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

## 10. API Integration Strategy

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

## 11. Local Development Model

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

## 12. Configuration Requirements

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

## 13. CI/CD Implications

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

## 14. Docker And Deployment Implications

AniBridge should not overcomplicate frontend delivery in the first iteration.

## 14.1 Development Docker

Add a frontend service to development compose only when the Web UI exists.

Suggested future service model:

- `web-dev` runs the Vite dev server
- proxies API calls to `api`
- can be enabled only in dev-oriented compose files

## 14.2 Production deployment options

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

## 14.3 Dockerfile strategy

Do not merge the frontend into the Python image.

Preferred future approach:

- separate Dockerfile for `apps/web` if containerized
- separate release artifact from `apps/api`

This keeps runtime responsibilities explicit.

## 15. Release And Versioning Implications

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

## 16. Testing Strategy

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

## 17. Design-System Guidance

The first Web UI should not try to become a giant abstract design system.

Recommended approach:

- define a small token set early
- standardize layout, spacing, typography, and state patterns
- keep most components local to `apps/web`
- extract shared UI only when a second app or true cross-surface reuse appears

This preserves speed while still giving the frontend a clean internal structure.

## 18. Security And Auth Considerations

The Web UI decision affects auth and deployment.

The frontend should assume:

- authenticated operations will exist or may exist later
- browser calls must respect backend auth/session design
- no business-critical authorization logic should live only in the frontend

Required follow-up once the UI starts:

- define auth model
- define CSRF/session/token expectations
- define cross-origin or same-origin deployment strategy

## 19. Recommended Implementation Sequence

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

## 20. Explicit Decisions

### Adopt now

- `apps/web` as the Web UI location
- React + TypeScript + Vite
- TanStack Router
- TanStack Query
- pnpm for Node workspace management
- generated API client from OpenAPI
- Vitest + Playwright + MSW

### Defer until concrete need exists

- Storybook
- charting library
- shared `packages/*`
- SSR framework adoption
- frontend independent versioning

## 21. Final Recommendation

AniBridge should build its first Web UI as a Vite-powered React application in
`apps/web`, backed by TanStack Router, TanStack Query, and an OpenAPI-generated
client.

This is the cleanest architecture for the current product because it:

- respects the existing FastAPI backend
- avoids duplicating server responsibilities
- gives strong TypeScript ergonomics
- scales well for an admin/operator interface
- keeps deployment and local development simpler than a full-stack React
  meta-framework

If the product later grows into a public, SEO-heavy, SSR-dependent web surface,
that should trigger a new architecture decision. It should not be assumed now.

## 22. References

- Vite getting started: https://vite.dev/guide/
- Vite SSR guide: https://vite.dev/guide/ssr.html
- TanStack Router overview: https://tanstack.com/router/learn/docs/framework/react/overview
- TanStack Query docs: https://tanstack.com/query/latest/docs/react/
- React Query guide on queries: https://tanstack.com/query/v5/docs/framework/react/guides/queries
- Orval React Query generation: https://orval.dev/docs/guides/react-query
- Vitest docs: https://main.vitest.dev/
- Playwright docs: https://playwright.dev/
- MSW docs: https://mswjs.io/
- Storybook docs: https://storybook.js.org/docs
