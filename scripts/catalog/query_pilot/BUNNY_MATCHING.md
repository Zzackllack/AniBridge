# Retained Bunny Girl Senpai discovery pilot

Uses the maintainer-selected AniWorld title and the existing
`anibridge-query-bunny-pilot` volumes. Collection is already complete for the
observed 29 entries/70 language variants. Startup below does not collect again.
Do not mix this project's volumes with the generated Breaking Bad rehearsal.

The resume-label fix is commit `0ce826fd30eba0cf8c0772a53e0695331028feb0`.
Its tested images are retained locally; build that revision first if needed.
Docker became unavailable after the discovery checks, so the final queue/status check
could not run. No volume deletion or media grab command was issued.

## Validated correspondence

The collected explicit IMDb ID `tt8993398` matched exactly one Skyhook candidate,
TVDB **345596**, with matching title/year and descriptor IMDb ID. TMDB TV
**82739** was also supplied by that descriptor. Provider numbering alone did
not establish either season correspondence:

| Source group | Accepted canonical group | Evidence | Discovery |
| --- | --- | --- | --- |
| Season 1 | TVDB 345596, season 1 | 13 unique exact normalized episode-title matches | 39 language variants, episodes 1–13 |
| Season 2 | TVDB 345596, season 2 | 12 unique exact normalized episode-title matches | 23 language variants, episodes 1–12; partial |
| Season 2 episode 13 | Unresolved | `[Final Episode]` annotation prevents an exact title match | Not returned by canonical season search |
| Three film entries | Unresolved | `[Movie]` annotations; no film/special correspondence accepted | Retained in raw title search |

Reviewed season correspondence uses the existing `--review-season` contract;
episode coordinates come from the validated descriptor's unique titles.
No suffix stripping, ordinal equality or guessed special numbers were applied.
All 70 release identities, source entity/language associations and first-seen
timestamps remained identical (digest recorded in the evidence JSON).
The prior worker ledger is retained as
`/state/aniworld.to.sqlite.before-sonarr-matching.backup`. No old volume was reset.

## Repeat discovery only

Run from the repository root after starting Docker. These commands reuse the
saved matching configuration and disposable client volumes. They add an
unmonitored series with an Unknown-only profile if it is absent; descriptor/
artwork lookups may occur. The script issues interactive searches, never a
release POST or a download command.

```sh
export PILOT_COMMIT=0ce826fd30eba0cf8c0772a53e0695331028feb0
export PILOT_PROVIDER_ORIGIN=https://aniworld.to
export PILOT_SOURCE_ID=private-bunny-pilot
export PILOT_CANONICAL_TV=skyhook
export COMPOSE_FILE=scripts/catalog/query_pilot/compose.yaml:scripts/catalog/query_pilot/show.yaml:scripts/catalog/query_pilot/clients.yaml
docker compose -p anibridge-query-bunny-pilot up -d catalog api sonarr prowlarr
docker compose -p anibridge-query-bunny-pilot exec -T --user 1000 api \
  python /pilot/clients.py --tvdb-id 345596 --season 1 --episode 1 \
  --expected-season-releases 39 --expected-episode-releases 3 \
  --episode-search --season-search
docker compose -p anibridge-query-bunny-pilot exec -T api \
  python -c 'import httpx; h=httpx.Client(trust_env=False); r=h.get("http://127.0.0.1:8000/api/v2/torrents/info"); r.raise_for_status(); print(r.json())'
docker compose -p anibridge-query-bunny-pilot down
```

Expected: both indexer tests HTTP 200; Prowlarr forwards 39 season releases;
Sonarr matches three episode-1 releases and 39 season releases to local series
identity, season 1, episodes 1–13, all Unknown quality. Queue expectation: `[]`;
the post-discovery queue check remains unverified until Docker is available.
`down` retains all volumes. Do not use `down -v` while retaining this pilot.

The next mapping work is a specific review of the annotated final episode and
film/special identities, not a numbering fallback. Extraction, grab completion,
import and playback remain untested. Full commands/results/limits are in
[EVIDENCE.md](../../../internal/specs/020-catalog-query-api-evaluation/EVIDENCE.md).
