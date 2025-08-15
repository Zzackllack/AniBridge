# AGENTS

AniBridge is a FastAPI-based service that bridges anime sources to automation tools.

## Repository layout
- `app/` – core application modules (scheduler, APIs, etc.)
- `docker-compose*.yaml`, `Dockerfile` – container definitions
- `requirements.txt` – Python dependencies
- Docs: `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, etc.

## Contribution guidelines
- Use `rg` for searching the codebase.
- Format Python code with `black` and keep imports tidy.
- Update documentation and comments when behavior changes.
- Prefer adding tests for new features or bug fixes.

## Validation
- Run `pytest` before committing. The project currently has limited tests; expand coverage when possible.
- Ensure the application starts via `uvicorn app.main:app --reload` or `docker compose up`.

## Migration notes
- Test coverage and type hints are being introduced gradually. Please help improve them when touching relevant areas.
