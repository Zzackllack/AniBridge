---
title: S.to (SerienStream)
outline: deep
---

# S.to Provider

<div class="provider-banner">
  <img src="./img/sto.png" alt="S.to banner image" />
</div>

::: danger Legal And Jurisdiction Notice
Before enabling this provider, read the [Legal Disclaimer](/legal).  
You are responsible for ensuring that access, automation, and downloads are legal in your jurisdiction and allowed by the third-party service terms.
:::

If you are setting up AniBridge for TV/series automation, S.to (SerienStream) is one of the supported providers.

## Quick User Summary

S.to is the short-domain branding of SerienStream and is widely used as a German-language TV/series index.

## Background And History

- **19 Jan 2015** – The project launches under the domain `SerienStream.to`, offering a dedicated index for TV series to separate itself from movie-focused portals. [Wikipedia (DE)](https://de.wikipedia.org/wiki/SerienStream.to)
- **22 Mar 2018** – The primary domain is switched to the short URL `s.to`. This rebrand becomes the site's permanent identity, though the original long domain remains active as a redirect.
- **Dec 2018** – First major ISP blocks occur in Austria (specifically T-Mobile Austria), marking the start of regulator-backed DNS blocking in the DACH region.
- **11 Mar 2021** – Operators publish the "DNS Zensur" support article, confirming that German ISPs (Telekom, Vodafone, 1&1) have begun blocking the domain following a **CUII** (Clearingstelle Urheberrecht im Internet) recommendation from Feb 2021.
- **31 Jan 2026** – Official announcement of **"Version2"**, a complete infrastructure rewrite. The update modernizes the backend while preserving user watchlists and accounts, securing the platform for the next decade.

For users, this history is useful context: domain changes, blocks, or infrastructure updates can affect setup stability even if your AniBridge config is correct.

## What You Can Expect In AniBridge

- AniBridge can resolve S.to slugs from your queries.
- It can target episodes by `(slug, season, episode)`.
- It parses available hosters and language variants from episode pages.
- It uses this data to build Torznab items and download jobs.

## Practical Notes For Setup

- Provider key in config: `s.to`
- Slugs typically follow: `/serie/<slug>`
- AniBridge can read a live alphabet page or local HTML fallback for title indexing.
- Default language candidates in AniBridge:
  - `German Dub`
  - `English Dub`
  - `German Sub`

## Episode Provider Parsing (S.to v2)

AniBridge includes S.to-specific parsing for episode pages. In practical terms, this means AniBridge can discover available hosters and language options directly from the provider page:

- builds episode URLs as `/serie/<slug>/staffel-<season>/episode-<episode>`
- extracts `data-play-url`, provider name, and language metadata
- maps language IDs to AniBridge language labels
- enriches episode objects with provider/language choices used later for resolution

## Configuration

Common environment variables:

- `CATALOG_SITES` (include `s.to` to enable)
- `STO_BASE_URL`
- `STO_ALPHABET_URL`
- `STO_ALPHABET_HTML`
- `STO_TITLES_REFRESH_HOURS`

See [Environment](/api/environment) for full definitions.

## Things To Keep In Mind

- Provider markup changes can affect parser results until AniBridge is updated.
- Availability, language options, and hosters are provider-controlled and can change at any time.
- Legal and provider-policy status can change. Re-check before long-term automation.
