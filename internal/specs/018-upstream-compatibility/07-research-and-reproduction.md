# Research sources, reproduction, and open questions

## Source ledger

### AniBridge

- [Repository at research base](https://github.com/Zzackllack/AniBridge/tree/1c9b3b9396a0c9c5c55217323b52272e5acb87b2)
- [Remote main comparison](https://github.com/Zzackllack/AniBridge/compare/1c9b3b9396a0c9c5c55217323b52272e5acb87b2...1b0370915243f86c020c62bfc336aa0f46eda2c3)
- [Issue #158: s.to resolution](https://github.com/Zzackllack/AniBridge/issues/158)
- [Issue #52: monitoring dashboard](https://github.com/Zzackllack/AniBridge/issues/52)
- [PR #119: provider catalog index](https://github.com/Zzackllack/AniBridge/pull/119)
- Local `internal/specs/007-sto-v2-support/`: historical provider migration context.
- Local `internal/specs/010-strm-proxy-stream/`: separate proxy/session contract context.
- Local `internal/specs/012-specials-extras/`: special episode mapping context.
- Local `internal/specs/013-fix-season-search/`: fast season search and performance context.
- Local `internal/specs/015-web-ui-foundation/`: exploratory future WebUI; not this implementation.

Existing specifications are context, not proof that proposed features exist. The active main source and its tests determine today's behavior.

### Upstream primary sources

- [5.0.6 release](https://github.com/phoenixthrush/AniWorld-Downloader/releases/tag/v.5.0.6)
- [4.2.1→5.0.6 comparison](https://github.com/phoenixthrush/AniWorld-Downloader/compare/v.4.2.1...v.5.0.6)
- [PyPI metadata](https://pypi.org/pypi/aniworld/5.0.6/json)
- [Tagged project metadata](https://github.com/phoenixthrush/AniWorld-Downloader/blob/v.5.0.6/pyproject.toml)
- [Tagged config](https://github.com/phoenixthrush/AniWorld-Downloader/blob/v.5.0.6/src/aniworld/config.py)
- [Environment initialization](https://github.com/phoenixthrush/AniWorld-Downloader/blob/v.5.0.6/src/aniworld/env.py)
- [Serienstream episode model](https://github.com/phoenixthrush/AniWorld-Downloader/blob/v.5.0.6/src/aniworld/models/s_to/episode.py)
- [Serienstream transport](https://github.com/phoenixthrush/AniWorld-Downloader/blob/v.5.0.6/src/aniworld/models/s_to/http.py)
- [AniWorld episode model](https://github.com/phoenixthrush/AniWorld-Downloader/blob/v.5.0.6/src/aniworld/models/aniworld_to/episode.py)
- [VOE extractor](https://github.com/phoenixthrush/AniWorld-Downloader/blob/v.5.0.6/src/aniworld/extractors/provider/voe.py)
- [Extractor registry](https://github.com/phoenixthrush/AniWorld-Downloader/blob/v.5.0.6/src/aniworld/extractors/__init__.py)
- [Browser helper](https://github.com/phoenixthrush/AniWorld-Downloader/blob/v.5.0.6/src/aniworld/playwright/captcha.py)
- [Upstream Dockerfile](https://github.com/phoenixthrush/AniWorld-Downloader/blob/v.5.0.6/Dockerfile)
- [Upstream issue #305](https://github.com/phoenixthrush/AniWorld-Downloader/issues/305): reporter evidence of missing Chromium and s.to/VOE challenges, not an AniBridge reproduction.

### Tool documentation consulted through Context7

AniWorld-Downloader lookup returned unrelated libraries, so no fabricated Context7 library ID was used. Tagged source inspection replaced missing package documentation.

uv lookup resolved `/astral-sh/uv`. Relevant official docs:

- [Locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
- [Dependencies](https://docs.astral.sh/uv/concepts/projects/dependencies/)
- [Docker integration](https://docs.astral.sh/uv/guides/integration/docker/)

`--frozen` uses the lock without checking it matches project metadata. `--locked` checks that the lock need not change. `--no-install-project` skips only installation of the root package, not its dependencies. `--upgrade-package` targets the chosen dependency; inspect its transitive changes anyway.

## Reproduce the comparison safely

Use fresh temporary checkouts to avoid local .env files, cached provider pages, credentials, and an existing .venv. These commands create local research copies and reuse an existing commit; they do not create commits or change the working branch.

```sh
repo_root=/absolute/path/to/AniBridge
research_root=$(mktemp -d /tmp/anibridge-upstream-research.XXXXXX)
base_ref=1c9b3b9396a0c9c5c55217323b52272e5acb87b2

git clone --no-hardlinks "$repo_root" "$research_root/baseline"
git -C "$research_root/baseline" checkout --detach "$base_ref"
git clone --no-hardlinks "$repo_root" "$research_root/candidate"
git -C "$research_root/candidate" checkout --detach "$base_ref"

uv sync --project "$research_root/baseline/apps/api" --frozen --no-install-project
```

Change only the temporary candidate pyproject constraint from `aniworld==4.2.1` to `aniworld==5.0.6`. Then:

```sh
uv lock --project "$research_root/candidate/apps/api" --upgrade-package aniworld
uv sync --project "$research_root/candidate/apps/api" --frozen --no-install-project
```

Run from each checkout's `apps/api` directory with its own `.venv/bin/python`. On Windows use the corresponding Scripts executable. Do not globally override DATA_DIR/DOWNLOAD_DIR for the full suite: the configuration-default test expects repository-relative paths, which are safe inside these disposable copies.

```sh
env -u DATA_DIR -u DOWNLOAD_DIR   ANIWORLD_INSTALL_FOLDER="$research_root/upstream-baseline"   ANIBRIDGE_TEST_MODE=1 ANIBRIDGE_UPDATE_CHECK=0 PUBLIC_IP_CHECK_ENABLED=0   .venv/bin/python -m pytest -o addopts='' -q
uv sync --frozen --no-editable
uv pip check --python .venv/bin/python
```

Use a distinct ANIWORLD_INSTALL_FOLDER for the candidate. Fresh clones have Git metadata needed by release-helper tests; archive-only copies do not. For implementation, use the *current* main base and update the evidence instead of using this historical base indefinitely.

## Executed probe methodology

Real-package probe: imported actual upstream models/config/registry in a fresh process, created real episode models, and seeded a synthetic provider map only to exercise language and redirect contracts without live requests. It did not claim that seeded data tests upstream HTML parsing. The complete harness appears below so an implementer can reproduce or replace it with permanent tests.

Live probe: built an AniBridge episode for each recorded example, resolved German Dub through VOE, requested the returned URL with streaming HTTP, checked status and the first 2048-byte chunk for `#EXTM3U`, and closed the response without downloading video segments. Explicit DATA_DIR/DOWNLOAD_DIR and upstream config folders isolated these probes. Local redirect retries were disabled and timeout reduced for research. The script's upstream calls can still have their own deadlines; use an outer subprocess timeout in future automation.

Transport probe: supplied a fake Session to upstream `sto_get`. The first two HTTPS domain calls raised synthetic errors. The third returned a synthetic HTTP 403 object. Upstream called the raw-IP URL with `verify=False` and returned the object. No network request was sent in this experiment. See [serienstream-transport.json](evidence/serienstream-transport.json). This confirms both the transport policy change and the missing final status check.

## Decisions the evidence cannot settle

| Question | Current answer | Required next evidence |
| --- | --- | --- |
| Does upgrade fix #158? | Not established; both versions work locally | Failing response classification and matched environment reproduction |
| Should browser support ship now? | No, separate feature | Provisioning/session/resource design and tests |
| Does a bare URL suffice for every host? | Only tested examples | Required-header/cookie contract tests per supported path |
| Can Linux images run new native deps? | Wheels exist; daemon unavailable | Actual amd64/arm64 builds and runtime smoke |
| Are binary resources bundled? | Not verified | Real release command and installed-binary smoke |
| Is full Sonarr import healthy? | Not verified | G7 end-to-end trace |
| Are Megakino/other hosts healthy? | Not established here | Bounded separate live checks |
| Is upstream still 5.0.6 later? | Checked 2026-09-20 only | Recheck before implementation |
| Is startup memory acceptable? | Not measured | Container process/memory observations; separate catalog benchmark later |

## Research limitations and correction policy

Do not transform hypotheses into facts in implementation notes. In particular, HTTP 200 can be a challenge but is not by itself proof of one; a hostname at the failing stage does not identify the firewall vendor; changing IP is strong evidence of network-dependent behavior but is not a capture of the response.

No full catalog crawl, production deployment, source media download, browser solving, or *arr client setup was undertaken here. The absence of those tests is explicit. This handoff is extensive enough to start implementation, but release readiness requires the remaining gates.

All temporary raw logs, generated upstream config, HTML, cookies, or resolved links must stay outside the repository. Only sanitized structured summaries are suitable for evidence. The memory and earlier conversation were used to choose investigation questions; current claims are tied to this run or explicitly identified reporter evidence.

## Complete real-package shape probe

Run this from an isolated checkout's `apps/api` directory with its environment and temporary DATA_DIR, DOWNLOAD_DIR, ANIWORLD_INSTALL_FOLDER, and STO_BASE_URL set. It is a research harness, not recommended production code. Private-cache seeding is confined to the experiment.

```python
import importlib, inspect, json, os, sys, time
from pathlib import Path
from importlib.metadata import version
sys.path.insert(0,str(Path.cwd()))
from loguru import logger
logger.remove()
t=time.monotonic()
import aniworld.models as models
import aniworld.config as cfg
import aniworld.extractors as extractors
from app.core.downloader.episode import build_episode
logger.remove()
result={'version':version('aniworld'),'import_seconds':round(time.monotonic()-t,3),'legacy_episode':hasattr(models,'Episode'),'symbols':{},'episodes':{},'config_dir':str(getattr(cfg,'ANIWORLD_CONFIG_DIR','not exposed'))}
for n in ('GLOBAL_SESSION','DEFAULT_USER_AGENT','PROVIDER_HEADERS_D','INVERSE_LANG_KEY_MAP','LANG_LABELS','INVERSE_LANG_LABELS','LANG_KEY_MAP'):
 result['symbols'][n]=hasattr(cfg,n)
for host in ('voe','filemoon','streamtape','vidmoly','doodstream','loadx','luluvdo','vidoza'):
 name='get_direct_link_from_'+host
 f=extractors.provider_functions.get(name)
 result['symbols'][name]=str(inspect.signature(f)) if f else None
for site,slug in [('aniworld.to','one-piece'),('s.to','avatar-herr-der-elemente-2024')]:
 x=build_episode(site=site,slug=slug,season=1,episode=1)
 backend=x._backend
 module=importlib.import_module(type(backend).__module__)
 audio=getattr(module,"Audio",cfg.Audio); subtitles=getattr(module,"Subtitles",cfg.Subtitles)
 key=(audio.GERMAN,subtitles.NONE)
 raw={key:{'VOE':'https://example.org/redirect'}}
 # Seed only provider data, retaining installed model classes and enums.
 setattr(backend,'_'+type(backend).__name__+'__provider_data',raw)
 labels=x.available_languages
 norm=x._normalize_language_for_backend('German Dub')
 result['episodes'][site]={'backend':type(backend).__name__,'languages':labels,'redirect_matches':x._get_provider_redirect_url(norm,'VOE')=='https://example.org/redirect'}
# Synthetic parser variants: no downloaded provider data in the evidence.
from aniworld.extractors.provider.voe import extract_voe_source_from_html
result['plain_hls_parsed']=extract_voe_source_from_html("<script>var sources = {'hls': 'https://example.org/master.m3u8'};</script>")=='https://example.org/master.m3u8'
print(json.dumps(result,indent=2))
```

## Complete transport-policy probe

This executes no network requests. It uses the installed candidate package and a temporary ANIWORLD_INSTALL_FOLDER.

```python
import json
from types import SimpleNamespace
from aniworld.models.s_to import http
class Session:
 def __init__(self): self.calls=[]
 def get(self,url,**kw):
  self.calls.append({'url':url,'verify':kw.get('verify',True),'host_header':kw.get('headers',{}).get('Host')})
  if len(self.calls)<3: raise OSError('synthetic failure')
  return SimpleNamespace(status_code=403,text='synthetic block')
s=Session();r=http.sto_get('https://serienstream.to/serie/test/staffel-1/episode-1',session=s)
print(json.dumps({'calls':s.calls,'returned_status':r.status_code},indent=2))
```
