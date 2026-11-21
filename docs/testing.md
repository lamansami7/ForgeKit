# Testing guide

## Running the suite

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pytest                                   # full suite
pytest tests/test_backup_safety.py -q    # one module
pytest -k "restore" -q                   # by name
pytest --cov=forgekit --cov-report=term-missing   # with coverage
ruff check src/ tests/
ruff format --check src/ tests/
```

Requirements: no internet, no root, no real package manager writes. Tests that
need a Git repository create a throwaway one in `tmp_path`. Every test runs with
`HOME`, `XDG_CONFIG_HOME` and `XDG_CACHE_HOME` redirected into a temporary
directory (see `tests/conftest.py`), so the developer's real configuration is
never read or written.

## Layout

| Test module | Focus |
|-------------|-------|
| `test_backup.py`, `test_backup_safety.py` | creation, verification, malicious archives, traversal, conflicts |
| `test_backup_transaction.py` | journaled restore, rollback, interrupted restores |
| `test_config.py`, `test_config_safety.py` | schema, validation, atomic writes, symlink refusal |
| `test_workspace.py` | scaffolding, force semantics, path safety |
| `test_filesystem_safety.py`, `test_files.py` | traversal, symlinks, size/hash behaviour |
| `test_network*.py`, `test_dns.py`, `test_ports.py` | resolution, HTTP, ports, timeouts, redaction |
| `test_git*.py` | porcelain parsing, credentials, failure modes |
| `test_security.py`, `test_packages.py`, `test_developer.py` | checks, manager detection and parsing |
| `test_cli_json_matrix.py` | JSON output and exit-code contracts |
| `test_cli_text_output.py`, `test_cli_more_paths.py` | human-readable rendering for every command |
| `test_services_edge_cases.py` | missing tools, denied permissions, odd environments |
| `test_storage.py` | opt-in cache and history helpers |

## Mocking strategy

- Network calls are mocked with `monkeypatch` on the command/service function, so
  no test depends on the internet.
- External binaries (`apt`, `dnf`, `pacman`, `ping`, `git`) are replaced with fake
  `shutil.which`/`subprocess.run` implementations.
- Filesystem danger cases use real temporary directories rather than mocks, so the
  kernel's symlink and permission behaviour is exercised.
- Failure injection monkeypatches internal helpers (for example `_restore_file`) to
  simulate disk exhaustion and I/O errors mid-operation.

## Coverage policy

- The gate is **90% of statements** (`[tool.coverage.report] fail_under = 90` in
  `pyproject.toml`); CI fails below it.
- Coverage is a floor, not a goal: new tests must assert behaviour. Do not add
  tests that only execute lines.
- The remaining uncovered lines are platform-specific branches (`Windows`/
  `Darwin` paths), `python -m forgekit`'s `__main__` guard, and defensive
  exception handlers that require simulating OS failures.

## Adding a test

1. Put it in the module that matches its area, or create one following the naming
   scheme above.
2. Use `tmp_path` for filesystem work and `monkeypatch` for the environment.
3. Assert on observable behaviour (files on disk, JSON keys, exit codes, error
   text), not on implementation details.
4. Run `ruff format src/ tests/ && ruff check src/ tests/ && pytest` before
   opening a pull request.
