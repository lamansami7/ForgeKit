# Architecture

## Overview

ForgeKit is a modular Python CLI built with Typer (CLI) + Rich (terminal) + psutil (system).

```
src/forgekit/
  cli.py              — root Typer app, global options, banners, subcommand wiring
  config.py           — ForgeConfig dataclasses, TOML load/save/validate
  constants.py        — thresholds, paths, banner
  exceptions.py       — typed errors
  output.py           — Rich tables/panels + JSON printing
  utils.py            — format_bytes, run_command, which, redact_url
  platform.py         — OS detection, user/hostname
  logging.py          — setup
  core/               — runner context, checks, permissions, environment
  services/           — business logic (system, network, git, filesystem, package, security, backup, developer)
  models/             — dataclass models with to_dict()
  commands/           — Typer sub-apps (system, net, git, files, packages, dev, security, backup, workspace, doctor, dashboard, info, config)
  storage/            — optional SQLite history + file cache
  resources/          — static assets (empty, extensible)
```

## Design Principles

- **Linux-first, cross-platform aware** — `platform.py` abstracts OS; commands explain when unsupported.
- **Services vs Commands** — Services are testable, I/O-free logic; Commands handle CLI + rendering.
- **Safe defaults** — read-only scans, no auto-delete, overwrite protection, credential redaction.
- **JSON everywhere** — `--json` returns structured data without Rich markup.
- **Mocks in tests** — network/hardware/package managers mocked; no internet/root needed.

## Adding a Command

1. Create `src/forgekit/services/my_service.py`
2. Create `src/forgekit/commands/my_command.py` with a Typer `app`
3. Add models in `src/forgekit/models/` if needed
4. Wire in `src/forgekit/cli.py`: `app.add_typer(my_app, name="mycommand")`
5. Add tests in `tests/test_my.py`

## Configuration

- Location: `~/.config/forgekit/config.toml`
- Dataclass `ForgeConfig` with sections: general, dashboard, thresholds, backup, files, network
- TOML via `tomllib` load + `tomli_w` (or manual fallback) save + `validate()` method.

## Error Handling

- Exceptions subclass `ForgeKitError` with `exit_code`.
- CLI catches and prints human-readable errors with exit 1.

## Packaging

- `pyproject.toml` with Hatchling, `forge` entry point, `requires-python >=3.11`
- Optional `dev` dependencies: pytest, ruff
