# Contributing to AniBridge

Thank you for your interest in improving AniBridge! The following guidelines will help you get
started.

## Code of Conduct

Please read and adhere to our [Code of Conduct](CODE_OF_CONDUCT.md).

## Development Setup

```bash
git clone https://github.com/zzackllack/AniBridge.git
cd AniBridge
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the application locally with:

```bash
python -m app.main
```

## Testing

Before submitting a pull request ensure that all tests pass:

```bash
pytest
```

## Code Style

- Format Python code with `black`.
- Keep imports tidy and avoid unused code.
- Update documentation and comments when behavior changes.

## Commit Messages

We follow the Conventional Commits specification: https://www.conventionalcommits.org/en/v1.0.0/#specification

## Pull Request Process

1. Fork the repository and create a new branch.
2. Make your changes, including tests and docs.
3. Run `black` on modified files and execute `pytest`.
4. Commit with clear messages and push your branch.
5. Open a Pull Request describing your changes.

## Questions?

Feel free to open an issue if you need help with contributing.
