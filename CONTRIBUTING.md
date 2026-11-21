# Contributing to ForgeKit

Thank you for contributing!

## Development Setup

```bash
git clone https://github.com/lamansami7/ForgeKit.git
cd ForgeKit
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
forge doctor
```

## Workflow

1. Fork and create a branch: `git checkout -b feat/my-feature`
2. Implement your change with type hints and clear error handling.
3. Add tests under `tests/` (mocks for network/hardware).
4. Run checks:

```bash
ruff check src/ tests/
ruff format --check src/ tests/
pytest --cov=forgekit --cov-report=term-missing
python -m build
```

5. Push and open a Pull Request against `main`.

## Guidelines

- No destructive defaults — explicitly authorize overwrite; test malicious archives, symlinks and existing files with temporary directories.
- Never silently transmit or delete user data.
- All commands must work or explain why they are unsupported (platform-aware). Linux is the primary target; do not claim untested macOS or Windows support.
- Use Rich tables/panels for terminal output and provide `--json` where useful.
- Keep commands consistent: `--help`, `--json`, proper exit codes.
- Add docs to `docs/` if you change behavior.

## Commit Messages

Use conventional prefixes: `feat:`, `fix:`, `docs:`, `test:`, `chore:`.

## Code of Conduct

See `CODE_OF_CONDUCT.md`. Be respectful and inclusive.

## Reporting Issues

Use GitHub Issues with steps to reproduce, expected vs actual, and environment info (`forge doctor --verbose`); redact usernames, paths, hostnames and other sensitive details before posting.
