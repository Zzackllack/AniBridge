# Docs Site

## VitePress

- Location: `docs/`.
- Tooling: VitePress 2.0.0-alpha.12, Vue 3.5, Vite 7.
- Scripts:
  - `pnpm --prefix docs run dev`
  - `pnpm --prefix docs run build`
  - `pnpm --prefix docs run preview`
- Config: `docs/.vitepress/config.mts`.
- Theme: `docs/.vitepress/theme/index.ts` with `custom.css` and components.
- Build output: `docs/.vitepress/dist` (do not commit).

## Content Structure

- `docs/src/guide/*` — user guides.
- `docs/src/developer/*` — developer guides.
- `docs/src/api/*` — API docs.
- `docs/src/integrations/*` — integration guides.
- `docs/src/legal.md` — legal documentation.

## Documentation Editing Guide

- Edit Markdown under `docs/src/*`.
- Update navigation/sidebar in `docs/.vitepress/config.mts` for new pages.
- Custom components live under `docs/.vitepress/theme`.
- Mermaid diagrams (` ```mermaid ` fences) are transformed in
  `docs/.vitepress/config.mts` and rendered client-side from
  `docs/.vitepress/theme/index.ts` via Mermaid ESM from jsDelivr.
- Preview with `pnpm --prefix docs run dev`; build with `pnpm --prefix docs run build`.
- Update `wrangler.toml` if deployment structure changes.
- Document config changes in `docs/src/guide/configuration.md`.
- Keep docs aligned with code behavior and `AGENTS.md`.

## Cloudflare Workers (Docs Hosting)

- Config: `wrangler.toml`.
- Worker name: `anibridge-docs`.
- Routes: `anibridge-docs.zacklack.de`.
- Compatibility date: `2025-08-15`.
- Build command (Wrangler):
  - `npm --prefix docs ci --no-audit --no-fund && npm --prefix docs run build`
- Assets directory: `docs/.vitepress/dist` (binding `ASSETS`).
- Static assets are configured with `run_worker_first = true` so
  canonical/SEO middleware in the Worker runs on every request.
- Worker entry: `docs/worker.ts`.
- Worker enforces permanent canonical redirects (`.html`, `/index.html`,
  trailing slash -> clean URL) and sets SEO headers (`X-Robots-Tag`,
  sitemap `Link`) for crawl/index consistency.
