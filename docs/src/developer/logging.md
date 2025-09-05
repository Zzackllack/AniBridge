---
title: Logging
outline: deep
---

# Logging

AniBridge uses `loguru` for structured logs and a `TerminalLogger` to duplicate stdout/stderr to a session log file under `data/`.

## Where to find logs

- Console output (colorized)
- `data/terminal-YYYY-MM-DD.log` (color codes stripped)

## Progress Rendering (TTY vs non‑TTY)

- Interactive terminals (TTY): AniBridge renders a live progress bar using `tqdm` with speed and ETA.
- Non‑interactive (Docker, CI, logs): AniBridge logs one progress line every N percent (default 5%).

Environment toggles:
- `PROGRESS_FORCE_BAR`: set to `true` to force a bar even if stdout is not a TTY (useful under reloader pipes).
- `PROGRESS_STEP_PERCENT`: integer percent step for non‑TTY progress lines (default `5`).

Implementation notes:
- The `TerminalLogger` tees stdout/stderr to `data/terminal-*.log`.
- When a progress bar is active, its output is sent directly to the real terminal (not the tee), so the `.log` file is not flooded with redraw lines.
- Non‑TTY runs never create a bar; only stepped log lines are written.

## Controlling output

- `LOG_LEVEL`: default `INFO`; use `DEBUG` for deeper diagnostics.
- `ANIBRIDGE_LOG_PATH`: optional absolute path to the session log file.
- The logger is initialized early; `.env` is loaded before sinks are attached, so `LOG_LEVEL` is honored.

## Tips

- Check provider/language errors in downloader and probe logs
- Inspect Torznab with `t=caps` and `t=tvsearch`
- Tail the session log while debugging: `tail -f data/terminal-*.log`
