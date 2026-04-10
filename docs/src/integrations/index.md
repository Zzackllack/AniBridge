---
title: Integrations Overview
outline: deep
---

# Integrations Overview

AniBridge exposes compatibility surfaces intended to interoperate with external
 automation clients and upstream provider ecosystems. This section summarizes
the integration boundaries, the supported categories of counterparties, and the
documents you should consult before enabling any particular workflow.

::: danger Legal And Jurisdiction Notice
Before enabling any integration, read the [Legal and Compliance overview](/legal).
Operators remain solely responsible for ensuring that any access, automation,
download, or retention behavior is lawful in the relevant jurisdiction and
permitted under any applicable third-party terms.
:::

## Integration Classes

AniBridge documentation separates integrations into two categories:

- Client integrations:
  downstream automation tools that connect to AniBridge through Torznab-style
  or qBittorrent-compatible interfaces.
- Provider integrations:
  upstream content-source adapters whose availability, structure, and terms are
  external to AniBridge and may change without notice.

## Client Integrations

Client pages explain how to connect automation tools to AniBridge's exposed
interfaces and what operational behavior to expect after configuration.

- [Prowlarr](/integrations/clients/prowlarr)
- [Sonarr](/integrations/clients/sonarr)
- [Radarr](/integrations/clients/radarr)

## Provider Integrations

Provider pages describe the provider-specific assumptions, practical setup
considerations, and known constraints that may affect search, resolution, or
download workflows.

- [AniWorld](/integrations/providers/aniworld)
- [S.to](/integrations/providers/sto)
- [Megakino](/integrations/providers/megakino)

## Operational Caveat

AniBridge can document and implement compatibility behavior for supported
clients and providers, but it does not control third-party platform uptime,
layout changes, access restrictions, service terms, or independent legal
posture. Integration feasibility is therefore a technical and legal question,
not merely a configuration question.
