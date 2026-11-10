---
title: Filmo
outline: deep
---

# Filmo Provider

::: danger Legal And Jurisdiction Notice
Before enabling this provider, read the [Legal and Compliance
overview](/legal). You are responsible for ensuring that access, automation, and
downloads are legal in your jurisdiction and allowed by the third-party service
terms.
:::

Filmo is an optional movie provider for **catalog query mode only**. It adds
movie releases that Radarr can search and import through AniBridge's Torznab and
qBittorrent-compatible endpoints. It is not part of legacy search, and configuring
Filmo in legacy mode fails startup.

Enabling Filmo does not create movie mappings. Radarr ID searches need a published
`tmdb-movie` or `imdb` mapping for the movie; text searches can still return
unmapped titles.

## What You Can Expect

- Movie results use category `2000`.
- Each native source offer is preserved as an explicit variant. A movie can have
  several selectable releases that differ by host, audio, or declared quality.
- Only VOE and Byse offers are selectable. Other hosts are filtered out before
  counts and pagination.
- Declared audio languages, subtitle mode, subtitle languages, and quality labels
  are kept as source evidence. They are not measured from the downloaded file.
- Unknown audio (`und`) is not advertised as a known spoken language. Offers
  without a known audio track are not selectable through the Torznab language
  set.
- Multi-audio offers are one release and match any requested declared audio
  language.
- Subtitles are reported separately as soft, hard, none, or unknown. Subtitle
  claims are never reused as audio claims.
- A generic `WEB` or resolution-only quality claim is not forced into the release
  title when Radarr cannot represent it without guessing. It remains in Torznab
  attributes and the item description.

## Configuration

```ini
CATALOG_MODE=query
CATALOG_SITES=aniworld.to,s.to,megakino,filmo.to
FILMO_BASE_URL=https://filmo.to
```

The collector must also enable `filmo.to` and publish its metadata. The API
collector token, source ID, and origin are configured as described in
[Catalog Query Mode](/guide/catalog-query). `FILMO_BASE_URL` must match the
verified Filmo origin used for local grabs.

## Radarr Setup

1. Add the AniBridge Torznab endpoint as a movie indexer in Prowlarr/Radarr.
2. Add the AniBridge qBittorrent shim as the download client.
3. Use movie category `2000`.
4. Prefer ID searches when mappings exist; text search works for unmapped titles
   but automatic matching can be unreliable.

Filmo items expose `anibridge_*` attributes for host, source ID, audio, subtitles,
declared quality, and measured resolution when available. See
[Torznab API](/api/torznab#filmo-attributes).

## Resolution Behavior

Selecting a Filmo release does not download media through the metadata service.
AniBridge re-fetches the selected movie page locally, verifies that the chosen
variant still matches, obtains a same-origin session/CSRF token, and resolves the
exact offer before the local download starts. If the offer changed or is no longer
available, the job fails explicitly as a stale selection or extraction error
instead of grabbing a different release silently.

## Things To Keep In Mind

- Filmo page titles follow the provider's `Accept-Language` behavior; this is a
  catalog-title preference, not an audio-language filter. Collection currently
  uses one locale and does not join translated aliases automatically.
- Provider markup, host names, and available offers can change without notice.
- Filmo playback and downloads remain local; the collector only supplies
  metadata.
- Legal and provider-policy status can change. Re-check before long-term
  automation.
