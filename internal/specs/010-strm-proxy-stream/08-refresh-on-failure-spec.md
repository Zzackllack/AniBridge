# Refresh-On-Failure Spec

## Status

Draft

## Scope

Define failure categories that trigger URL re-resolution, the retry strategy, cache invalidation rules, and safety limits to prevent provider hammering.

## Last updated

2026-02-03

## Failure Categories (Baseline)

Use the categories already proposed in the issue and prior STRM proxy notes as the default set:

- HTTP 403, 404, 410, 451, 429
- Upstream timeouts or network errors
Evidence: `specs/010-strm-proxy-stream/github-issue.md:103` and `specs/006-fix-strm-files/context.md:65`.

## Refresh Policy (Draft)

1. On a refresh-eligible failure, re-resolve the direct URL using the same resolver logic as STRM generation.
2. Retry the upstream request once with the new URL.
3. If the retry succeeds, update cache and (if enabled) persistence mapping.
4. If the retry fails, return the second failure to the client with minimal delay.

## Retry Limits And Backoff

- Maximum retries per request: 1.
- Track recent failures per episode identity; if multiple failures happen within a short window, return failures without re-resolving to avoid provider abuse (circuit breaker).

## Cache Invalidation Rules

- On refresh-eligible failure, invalidate cache entries for that episode identity.
- On non-refresh failures (e.g., 500 from AniBridge, client disconnect), do not invalidate cache automatically.

## Safety Measures

- Rate-limit refresh attempts per identity (e.g., no more than 1 refresh per N minutes).
- Log refresh attempts with redaction of sensitive URLs.
- Ensure refresh attempts use the same proxy/VPN egress as resolver and downloads.

## Decision Gates

- Whether 401/403 should trigger provider fallback vs same-provider re-resolve.
- Whether 5xx errors from upstream should trigger refresh or not.
- Whether `HEAD` should be attempted before a full refresh to detect transient failures.
