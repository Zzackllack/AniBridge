---
title: Testing
outline: deep
---

# Testing

AniBridge ships Pytest tests for config, Torznab, qBittorrent shim, magnets, and title resolution.

## Run tests

```bash
cd apps/api
pytest -q
```

## Coverage

```bash
cd apps/api
pytest --cov=app --cov-report=term-missing
```

## Notes

- Tests use the SQLite DB under `DATA_DIR`; the engine is disposed at shutdown to avoid dangling connections.
- Some tests monkeypatch title sources — `ANIWORLD_ALPHABET_HTML` can point to a small HTML fixture.
