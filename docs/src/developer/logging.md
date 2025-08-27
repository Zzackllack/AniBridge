---
title: Logging
outline: deep
---

# Logging

AniBridge uses `loguru` for structured logs and a `TerminalLogger` to duplicate stdout/stderr to a session log file under `data/`.

## Where to find logs

- Console output (colorized)
- `data/terminal-YYYY-MM-DD.log` (color codes stripped)

## Tips

- Set `LOG_LEVEL` if needed (e.g., `DEBUG`)
- Check provider/language errors in downloader and probe logs
- Inspect Torznab XML by curling `t=caps` and `t=tvsearch`

