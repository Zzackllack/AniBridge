---
title: API Reference
outline: false
---

# API Reference

This section is organized around operation pages (one page per endpoint). Use the sidebar or the index below to jump to the operation you need.

## Base URL

`http://localhost:8000` (default development host)

> [!IMPORTANT]
> If `INDEXER_API_KEY` is set, include `apikey=...` on every Torznab request.

> [!TIP]
> STRM proxy endpoints (`/strm/*`) use their own auth settings via
> `STRM_PROXY_AUTH`.

## Browse Operations

<ApiOperations />
