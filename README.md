# ForgeKit

<div align="center">

```
  ███████╗ ██████╗ ██████╗  ██████╗ ███████╗ ██╗  ██╗██╗████████╗
  ██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝ ██║ ██╔╝██║╚══██╔══╝
  █████╗  ██║   ██║██████╔╝██║  ███╗█████╗   █████╔╝ ██║   ██║
  ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝   ██╔═██╗ ██║   ██║
  ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗ ██║  ██╗██║   ██║
  ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝ ╚═╝  ╚═╝╚═╝   ╚═╝
```

**A powerful modular command-line toolkit for Linux, developers, and system diagnostics.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](#testing)

</div>

---

## ✨ Features

ForgeKit is a production-quality terminal-native toolkit designed for Linux first, with forward-compatible design for macOS and Windows.

| Area | Commands | Description |
|------|----------|-------------|
| **System** | `forge system` | OS, CPU, memory, disk, processes — real `psutil` data |
| **Network** | `forge net` | Ping, DNS, ports, interfaces, HTTP diagnostics, connectivity check |
| **Git** | `forge git` | Status, history, branches, inspect — credential-safe |
| **Files** | `forge files` | Large files, search, size breakdown, empty dirs, duplicates (hashing) |
| **Packages** | `forge packages` | Detect apt/dnf/pacman/apk/brew, check updates (read-only) |
| **Developer** | `forge dev` | Detect Python/Node/Go/Docker/etc. + PATH diagnostics |
| **Security** | `forge security` | Non-invasive checks — SSH perms, world-writable, firewall, risky configs |
| **Backup** | `forge backup` | Create/verify/restore compressed archives with safety guards |
| **Workspace** | `forge workspace` | Scaffold Python/Node/generic projects with .gitignore templates |
| **Doctor** | `forge doctor` | Self-diagnostics — Python, deps, config, platform |
| **Dashboard** | `forge dashboard` | Live Rich terminal dashboard |
| **Config** | `forge config` | TOML config at `~/.config/forgekit/config.toml` |

All commands support `--json` for piping and `--help` for guidance. **No destructive operation runs without confirmation.**

---

## 📦 Installation

### From source (recommended for development)

```bash
git clone https://github.com/lamansami7/ForgeKit.git
cd ForgeKit
pip install .
forge --help
```

### Development install (editable)

```bash
pip install -e ".[dev]"
forge --help
pytest
ruff check src/ tests/
```

### Verify installation

```bash
forge --version
forge doctor
forge system --json | head
```

**Requirements:** Python 3.11+, Linux (primary), pip.

---

## 🚀 Quick Start

```bash
# System overview
forge
forge system
forge system cpu --per-core
forge system memory
forge system disk
forge system processes --sort memory --limit 5

# Network
forge net ping google.com
forge net dns google.com
forge net check
forge net ports
forge net interfaces
forge net http https://example.com --headers

# Git (inside a repo)
forge git
forge git status
forge git history --limit 10
forge git branches
forge git inspect path/to/file

# Files
forge files large /home/user --threshold 100
forge files search /home/user "*.log" --ext
forge files size /home/user/projects
forge files empty /tmp
forge files duplicates /home/user --min-size 1024

# Packages
forge packages
forge packages updates
forge packages list --limit 20

# Developer
forge dev
forge dev versions
forge dev check

# Security (read-only)
forge security
forge security --path ~/myproject
forge security scan path/to/config.ini

# Backup (with safety guards)
forge backup create ./mydata ./backups --compression gz
forge backup create ./mydata ./backups --dry-run
forge backup list ./backups/mydata-*.tar.gz
forge backup verify ./backups/mydata-*.tar.gz
forge backup restore ./backups/mydata.tar.gz ./restored --dry-run
forge backup restore ./backups/mydata.tar.gz ./restored --force

# Workspace
forge workspace templates
forge workspace create myapp --template python --path .
forge workspace create myapp --template node --path . --git
forge workspace inspect ./myapp

# Doctor & Dashboard
forge doctor --verbose
forge dashboard --refresh 1.5
forge dashboard --json

# Config
forge config show
forge config init
forge config validate
forge config get dashboard.refresh_interval
forge config set dashboard.refresh_interval 3.0
forge config path

# Info
forge info
forge info --json
```

---

## ⚙️ Configuration

ForgeKit stores configuration at `~/.config/forgekit/config.toml` (XDG).

```toml
[general]
output_format = "auto"
colors = true
log_level = "WARNING"

[dashboard]
refresh_interval = 2.0
show_network = true
show_processes = true

[thresholds]
cpu_warning = 80.0
memory_warning = 85.0
disk_warning = 85.0

[backup]
default_destination = "~/backups"
compression = "gz"

[files]
large_threshold_mb = 100
exclude_dirs = [".git", "__pycache__", ".venv", "venv", "node_modules", ".cache"]

[network]
ping_timeout = 5
http_timeout = 10
```

Manage via CLI:

```bash
forge config show
forge config show --json
forge config init          # create default
forge config validate
forge config get dashboard.refresh_interval
forge config set general.colors false
```

No secrets or passwords are stored in config.

---

## 📖 Documentation

- [Installation](docs/installation.md)
- [Commands](docs/commands.md)
- [Configuration](docs/configuration.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Architecture](docs/architecture.md)
- [Examples](docs/examples.md)

---

## 🧪 Testing

```bash
pip install -e ".[dev]"
pytest -v
pytest --cov=src/forgekit --cov-report=term-missing
ruff check src/ tests/
ruff format --check src/ tests/
```

Tests use mocks for network/hardware/package managers — no internet or root required, and no user data is deleted.

---

## 🛡️ Safety & Security

- **Read-only by default** — scanning, diagnostics, and checks never modify data.
- **No silent deletes** — duplicates never auto-delete; restore requires `--force` to overwrite.
- **No auto-install** — packages are only inspected, never installed/removed automatically.
- **No credentials leaked** — Git remote URLs are redacted, HTTP headers filtered.
- **No root required** — works without elevated privileges; explains when info is limited.
- **Non-invasive security checks** — no exploitation, cracking, or unauthorized scanning.

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

```bash
git checkout -b feat/my-feature
# make changes + tests
ruff check src/ && pytest
git push && open PR
```

---

## 📝 License

MIT — see [LICENSE](LICENSE).

---

## 🙏 Acknowledgments

Built with [Typer](https://typer.tiangolo.com/), [Rich](https://github.com/Textualize/rich), [psutil](https://github.com/giampaolo/psutil), [Requests](https://requests.readthedocs.io/).

