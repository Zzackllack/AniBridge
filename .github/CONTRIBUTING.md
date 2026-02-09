# Contributing to AniBridge

Thank you for your interest in improving AniBridge! The following guidelines will help you get
started.

## Code of Conduct

Please read and adhere to our [Code of Conduct](CODE_OF_CONDUCT.md).

## Development Setup

This repository uses [uv](https://docs.astral.sh/uv/). It is **highly recommended** to use it for development. Install it first if you haven't already:

### MacOS

```bash
brew install uv
```

### Linux/MacOS

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

*Or via winget:*

```powershell
winget install --id=astral-sh.uv  -e
```

### Setting up the development environment

```bash
git clone https://github.com/zzackllack/AniBridge.git
cd AniBridge
uv sync --frozen
```

Run the application locally with:

```bash
uv run python -m app.main
```

Or directly with Python:

```bash
python -m app.main
```

Test changes to github workflows using a tool like [act](https://github.com/nektos/act).

## Testing

Before submitting a pull request ensure that all tests pass:

```bash
pytest
```

## Code Style

- Follow Python Enhancement Proposals (PEPs) for style and best practices. Especially PEP 8 and PEP 257.
- Format Python code with `ruff format`. And lint with `ruff check`.
- Keep imports tidy and avoid unused code.
- Update documentation and comments when behavior changes.

## Commit Messages

We follow the Conventional Commits specification: https://www.conventionalcommits.org/en/v1.0.0/#specification

## Codeowners

The codeowners for this repository are listed in the [CODEOWNERS](/.github/CODEOWNERS) file. Please update it as necessary when making changes to the codebase.

Conventions and tips you should follow when editing the CODEOWNERS file:

- The last matching rule wins, so put broad rules first and narrow overrides later.
- Paths are repository-rooted and support `*` and `**` globs.
- Only `CODEOWNERS`, `.github/CODEOWNERS`, or `docs/CODEOWNERS` are recognized by GitHub.
- Use @org/team for teams.

## Pull Request Process

1. Fork the repository and create a new branch.
2. Make your changes, including tests and docs.
3. Run `ruff format` on modified files and execute `pytest`.
4. Commit with clear messages and push your branch.
5. Open a Pull Request describing your changes.

## Questions?

Feel free to open an issue if you need help with contributing.
