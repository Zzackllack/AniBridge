# Implementation results and remaining gates

Date: 2026-09-20 (Europe/Berlin). These results describe the committed local
branch. Nothing was pushed, deployed, published, or posted to GitHub.

## Identity and baseline

| Item | Result |
| --- | --- |
| Branch | `zzackllack-aux/upstream-compatibility` |
| Remote-main implementation base | `1b0370915243f86c020c62bfc336aa0f46eda2c3` |
| Specification commit after rebase | `e119a12de017b287af259bd5e4ef5b4577f558b6` |
| Local implementation | committed; working tree clean |
| Host | macOS arm64, CPython 3.14.7, uv 0.12.17 |
| Original dependency | `aniworld` 4.2.1 |
| Implemented dependency | `aniworld` 5.0.6 |

The upstream tag and PyPI release were refreshed before implementation. No
newer released version than 5.0.6 was available. The original-lock baseline was
reproduced from the exact remote-main SHA in an isolated checkout: 145 tests
passed with one pre-existing warning in 12.41 seconds.

## Implemented behavior

- The dependency and targeted lock graph are updated without replacing main's
  independent AnyIO, Mako, or SoupSieve versions.
- A local episode protocol keeps callers independent of removed/nonexistent
  generic upstream models. Serienstream metadata now uses the existing local
  button parser through a lazy source facade.
- Configured Serienstream origin, HTTPS verification, bounded redirects,
  public-address checks, status classification, and token-safe diagnostics are
  enforced locally. The upstream raw-IP `verify=False` fallback is not reached.
- VOE resolution uses the local HTTP/HTML path and the real 5.0.6 decoder. It
  never invokes Patchright in the default request path; a recognized challenge
  returns a typed error with a suggested retry interval.
- Language absence, host absence, verification, transient transport failure,
  terminal 404/410, and unrecognized successful markup remain distinct.
- `ANIWORLD_INSTALL_FOLDER` owns upstream `.env` and session state without
  mutating `HOME`; Compose defaults it to `/data/aniworld`.
- The downloader package uses lazy public exports so the local VOE host does not
  introduce an application-startup import cycle.
- Python distributions now package the `app` namespace, README, and license.
  A PyInstaller hook includes Alembic scripts loaded dynamically at startup.

Inspection found that the upstream Doodstream extractor uses `verify=False` in
both 4.2.1 and 5.0.6. That is an existing optional-host limitation, not the new
Serienstream transport regression controlled by this increment, and it was not
silently represented as fixed.

## Local validation evidence

| Gate | Classification | Result |
| --- | --- | --- |
| Original-main baseline | isolated real install | 145 passed, 1 warning |
| Candidate lock/install | non-editable real install | `uv lock --check`, `uv sync --locked --no-editable`, and `uv pip check` passed |
| Full suite | mocked plus real-package subprocesses | 172 passed; one Starlette deprecation warning and the pre-existing terminal-log shutdown ResourceWarning |
| Formatting/lint | local source | Ruff format/check passed; Pylint retained the repository's existing findings and scored 8.38/10 |
| Distribution | clean copied source, isolated venv | sdist/wheel built; wheel contained only `app.*`, license, and metadata; installed outside source; `app.main` imported; dependency check passed |
| PyInstaller | real release command, macOS arm64 | built after adding migration hook; outside-source startup returned `/health` status `ok`; database reached Alembic revision `20260204_0003` |
| Compose | static configuration | production and development Compose files rendered successfully |
| Documentation | local build | VitePress build passed with pre-existing highlighting/chunk warnings |
| Live AniWorld | live network, bounded | One Piece S01E01, German Dub, VOE: expected languages, HTTP 200, HLS prefix |
| Live Serienstream | live network, bounded | Avatar 2024 S02E01, German Dub, VOE on configured `https://serienstream.to`: expected languages, HTTP 200, HLS prefix |

The live checks fetched only an initial playlist chunk. They did not download
media segments or prove audio, naming, playback, qBittorrent completion, or
Sonarr import.

## Open validation gates

- Docker is installed, and both Compose configurations render, but the local
  daemon is unavailable. Linux amd64/arm64 image build, non-root container
  startup, process/memory inspection, and container health remain blocked.
- Linux and Windows PyInstaller outputs require their native CI runners. Only
  macOS arm64 was built and started locally.
- No actual challenge occurred on this network. Synthetic 200/403/429/503
  challenge fixtures prove bounded classification, not a live provider's exact
  challenge markup or session behavior.
- G7 remains unexecuted because the Docker-backed isolated Sonarr/Prowlarr stack
  could not be started and no lawful media fixture was selected. Consequently,
  real client connection tests, queue transitions, completed output, Sonarr
  association/import, STRM consumer playback, restart persistence, and
  cancellation/failure behavior still require evidence.
- The reporter's IP-dependent failure from issue #158 was not reproduced.
  Successful HLS resolution on this machine must not be described as fixing it.

To finish the release gates, start a usable Docker daemon, build both Linux
architectures from the exact eventual commit, run the isolated G7 stack with a
permitted fixture, and obtain native Linux/Windows PyInstaller CI evidence.
Preserve the prior image digest and configuration backup for rollback; this
change has no schema migration, and rolling back requires reverting the pin and
complete lock update together.
