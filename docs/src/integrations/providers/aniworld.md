---
title: AniWorld
outline: deep
---

# AniWorld Provider

::: danger Legal And Jurisdiction Notice
Before enabling this provider, read the [Legal Disclaimer](/legal).  
You are responsible for ensuring that access, automation, and downloads are legal in your jurisdiction and allowed by the third-party service terms.
:::

If you are setting up AniBridge for anime workflows, AniWorld is one of the main provider options.

## Quick User Summary

AniWorld (formerly AniCloud) is a German-language anime-focused platform. For most users, it is known for German Dub and German Sub availability, with some English-sub entries depending on title and hoster.

## Background And History

- **Early 2021** – Popular unofficial anime streaming sites like Anime4You shut down, creating demand for alternatives.  [firmenbild.com](https://firmenbild.com/firma/aniworld-to/)
- **Feb 2021** – AniCloud (also referred to as Animecloud) appears as a new anime streaming/aggregation site.  [AniWorld - Support](https://aniworld.to/support/frage/was-is-mit-der-alten-website-passiert)
- **7 April 2022** – Official announcement that AniCloud rebrands to **AniWorld**, with domain migration to AniWorld.to.  [AniWorld - Support](https://aniworld.to/support/frage/neu-aniworld-alt-anicloud)
- **Oct 2023** – AniWorld site updates legal and terms pages under the AniWorld brand.  [AniWorld - Regeln](https://aniworld.to/support/regeln)
- **Dec 2024** – Media coverage highlights AniWorld’s prominence and legality questions.  [GIGA](https://www.giga.de/artikel/aniworld-ist-der-streamingdienst-legal-oder-illegal--5j3c64qfjm)

Because branding and domains in this ecosystem can change quickly, treat these details as point-in-time context.

## What You Can Expect In AniBridge

- AniBridge can resolve AniWorld series slugs from your Sonarr/Prowlarr queries.
- Episode checks are performed per season/episode and language.
- Release names are generated so *arr tools can parse episodes more reliably.
- AniWorld specials (`/filme`) are handled with metadata-based mapping to reduce import mismatches.

## Practical Notes For Setup

- Provider key in config: `aniworld.to`
- Slugs typically follow: `/anime/stream/<slug>`
- AniBridge can pull title index data from a live alphabet URL or a local HTML fallback.
- Default language candidates in AniBridge:
  - `German Dub`
  - `German Sub`
  - `English Sub`

## Specials Handling

AniBridge includes dedicated mapping logic for AniWorld specials.  
When AniWorld source numbering differs from Sonarr metadata numbering, AniBridge can:

- probe/download with AniWorld source coordinates
- still emit Sonarr-facing alias numbering in release names

This behavior reduces import mismatches for specials and extras.

## Configuration

Common environment variables:

- `CATALOG_SITES` (include `aniworld.to` to enable)
- `ANIWORLD_BASE_URL`
- `ANIWORLD_ALPHABET_URL`
- `ANIWORLD_ALPHABET_HTML`
- `ANIWORLD_TITLES_REFRESH_HOURS`

Related specials-mapping controls are documented in:

- [Environment](/api/environment)

## Things To Keep In Mind

- AniBridge does not control AniWorld uptime, layout changes, or regional blocking.
- AniWorld-side changes can temporarily affect search quality or episode resolution.
- The legal situation and site terms may change. Re-check them regularly.
