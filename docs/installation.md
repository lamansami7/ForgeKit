# Installation

## Requirements

- Python 3.11+
- pip
- Linux (primary). macOS and Windows are experimental and not release-tested; safe restore and workspace creation require POSIX directory-relative APIs.

## Install from source

```bash
git clone https://github.com/lamansami7/ForgeKit.git
cd ForgeKit
pip install .
forge --version
```

## Install from a built artifact

```bash
python -m build                                  # creates dist/forgekit-<version>-py3-none-any.whl and .tar.gz
python -m venv /tmp/forge-verify
/tmp/forge-verify/bin/pip install dist/forgekit-<version>-py3-none-any.whl
/tmp/forge-verify/bin/pip check
/tmp/forge-verify/bin/forge doctor
```

Installing the sdist (`dist/forgekit-<version>.tar.gz`) exercises the build
backend and is checked in CI as well.

## Development install

```bash
pip install -e ".[dev]"
```

This installs pytest, coverage, Ruff and the build frontend in editable mode. For a clean isolated install, create and activate a virtual environment before running these commands.

## Verify

```bash
forge --help
forge --version
forge doctor
forge system
forge system memory --json | python -m json.tool
```

## Uninstall

```bash
pip uninstall forgekit
```

## Troubleshooting

- `forge: command not found` — ensure `~/.local/bin` is in PATH: `export PATH="$HOME/.local/bin:$PATH"`
- Permission errors — do not use `sudo pip`; use `--user` or a virtualenv.
- Missing dependencies — reinstall with `python -m pip install .` inside the intended environment.

See `troubleshooting.md` for more.
