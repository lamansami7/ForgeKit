# Installation

## Requirements

- Python 3.11+
- pip
- Linux (primary), macOS/Windows with limitations

## Install from source

```bash
git clone https://github.com/lamansami7/ForgeKit.git
cd ForgeKit
pip install .
forge --version
```

## Development install

```bash
pip install -e ".[dev]"
```

This installs with `pytest`, `ruff`, and editable mode.

## Verify

```bash
forge --help
forge doctor
forge system
```

## Uninstall

```bash
pip uninstall forgekit
```

## Troubleshooting

- `forge: command not found` — ensure `~/.local/bin` is in PATH: `export PATH="$HOME/.local/bin:$PATH"`
- Permission errors — do not use `sudo pip`; use `--user` or a virtualenv.
- Missing `psutil` — `pip install psutil` separately, then reinstall.

See `troubleshooting.md` for more.
