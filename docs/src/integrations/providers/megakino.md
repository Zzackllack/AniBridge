---
title: Megakino
outline: deep
---

# Megakino Provider

::: danger Legal And Jurisdiction Notice
Before enabling this provider, read the [Legal Disclaimer](/legal).  
You are responsible for ensuring that access, automation, and downloads are legal in your jurisdiction and allowed by the third-party service terms.
:::

If you are setting up AniBridge for movie/series sources beyond AniWorld/S.to, Megakino is an optional supported provider.

## Quick User Summary

Megakino is commonly used as a German-language movie/series index with embedded hosters. In AniBridge, it uses a dedicated integration path.

## Background And History

- **Late 2022** – Megakino emerges as a prominent German-language streaming indexer, filling the market gap for high-quality movie and series links. [Tarnkappe.info](https://tarnkappe.info/artikel/streaming/megakino-co-cuii-erwaegt-sperre-fuer-streaming-portal-288414.html)
- **27 Feb 2024** – The **CUII** (Clearingstelle Urheberrecht im Internet) issues a formal blocking recommendation for the primary domain `megakino.co` in Germany. [CUII - Recommendations](https://cuii.info/empfehlungen/)
- **Mid 2024** – The platform begins aggressive domain-hopping (moving to `.ltd`, `.fun`, and `.vip`) to evade DNS blocks from major German ISPs. [Internet-Beschwerdestelle](https://www.internet-beschwerdestelle.de/)
- **11 Sept 2024** – The Austrian regulatory body **RTR** authorizes Austrian ISPs to block a wide list of Megakino mirrors, including `.rip`, `.biz`, and `.men`.
- **Present** – Megakino continues to operate through a decentralized mirror system.

Because source reliability in this area is inconsistent, this page focuses on what users can reliably expect from AniBridge behavior.

## What You Can Expect In AniBridge

- AniBridge can load title/slug data from Megakino sitemaps.
- It can resolve slugs for movie and serial pages.
- Search uses a Megakino-native strategy.
- AniBridge attempts direct provider URL resolution and uses fallback behavior when needed.

## Practical Notes For Setup

- Provider key in config: `megakino`
- Slugs typically follow: `/(serials|films)/<id>-<slug>`
- AniBridge uses sitemap indexing for this provider (not alphabet-page parsing).
- Default language candidates in AniBridge:
  - `Deutsch`
  - `German Dub`

## Resolution Behavior

For direct URL resolution, AniBridge:

- resolves the canonical Megakino page for a slug
- extracts embedded provider URLs
- tries preferred provider first when configured
- falls back to iframe URL when no extractor returns a direct media URL

## Configuration

Common environment variables:

- `CATALOG_SITES` (include `megakino` to enable)
- `MEGAKINO_BASE_URL`
- `MEGAKINO_TITLES_REFRESH_HOURS`
- `MEGAKINO_DOMAIN_CHECK_INTERVAL_MIN`

See [Environment](/api/environment) for full definitions.

## Things To Keep In Mind

- Domain availability and sitemap structure can change over time.
- Search and resolution quality depend on provider responses and iframe hosters.
- Legal and provider-policy status can change. Re-check before long-term automation.
