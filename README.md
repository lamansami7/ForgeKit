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
[![CI](https://github.com/lamansami7/ForgeKit/actions/workflows/ci.yml/badge.svg)](https://github.com/lamansami7/ForgeKit/actions/workflows/ci.yml)

</div>

---

## ✨ Features

ForgeKit is an early-stage, terminal-native toolkit designed for Linux first. macOS and Windows are experimental and have not been validated to the same extent. Do not treat this pre-1.0 software as production-ready.

**Current status: 0.2.0, public alpha.** Linux is the only validated platform; see the [post-PR2 audit](docs/audit-2026-11-post-pr2.md) for exactly what was verified, what remains limited, and why this is an alpha rather than a beta.

| Area | Commands | Description |
|------|----------|-------------|
| **System** | `forge system` | OS, CPU, memory, disk, processes — real `psutil` data |
| **Network** | `forge net` | Ping, DNS, ports, interfaces, HTTP diagnostics, connectivity check |
| **Git** | `forge git` | Status, history, branches, inspect — best-effort credential redaction |
| **Files** | `forge files` | Large files, search, size breakdown, empty dirs, duplicates (hashing) |
| **Packages** | `forge packages` | Detect apt/dnf/pacman/apk/brew, check updates (read-only) |
| **Developer** | `forge dev` | Detect Python/Node/Go/Docker/etc. + PATH diagnostics |
| **Security** | `forge security` | Non-invasive checks — SSH perms, world-writable, firewall, risky configs |
| **Backup** | `forge backup` | Create/verify/restore compressed archives; restore is journaled and rolls back on failure |
| **Workspace** | `forge workspace` | Scaffold Python/Node/generic projects with .gitignore templates |
| **Doctor** | `forge doctor` | Self-diagnostics — Python, deps, config, platform |
| **Dashboard** | `forge dashboard` | Live Rich terminal dashboard |
| **Config** | `forge config` | TOML config at `~/.config/forgekit/config.toml` |

Commands provide `--help` and, where supported, `--json` for piping, with diagnostics on stderr so JSON stays clean. A global `forge --json` also selects JSON for commands that support it. Explicit `--json` also produces JSON for argument and early configuration errors; configuration-only JSON has limitations before configuration is loaded. Backup and workspace operations write files; `--force` explicitly permits overwriting existing regular files.

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
forge files search /home/user ".log" --ext
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
forge backup create ./mydata ./backups/mydata.tar.gz
forge backup list ./backups/mydata.tar.gz
forge backup verify ./backups/mydata.tar.gz
forge backup restore ./backups/mydata.tar.gz ./restored --dry-run
forge backup restore ./backups/mydata.tar.gz ./restored

# Workspace
forge workspace templates
forge workspace create myapp --template python --path .
forge workspace create my-node-app --template node --path . --git
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

ForgeKit stores configuration at `$XDG_CONFIG_HOME/forgekit/config.toml` when XDG_CONFIG_HOME is an absolute path, or `~/.config/forgekit/config.toml` otherwise. Use `forge --config PATH ...` for an alternate file.

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

Do not store secrets in this configuration file. Invalid TOML, unknown keys and invalid values are reported rather than silently replaced. `config set` preserves existing comments and writes atomically.

---

## 📖 Documentation

- [Installation](docs/installation.md)
- [Commands](docs/commands.md)
- [Configuration](docs/configuration.md)
- [Backup safety and recovery](docs/backup-safety.md)
- [Platform support](docs/platform-support.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Architecture](docs/architecture.md)
- [Examples](docs/examples.md)
- [Testing](docs/testing.md)
- [Release checklist](docs/release-checklist.md) and [release procedure](docs/release-procedure.md)
- [Post-PR2 audit](docs/audit-2026-11-post-pr2.md)

---

## 🧪 Testing

```bash
pip install -e ".[dev]"
pytest
pytest --cov=forgekit --cov-report=term-missing   # gate: 90% statements
ruff check src/ tests/
ruff format --check src/ tests/
```

The suite currently runs 396 tests at 91% statement coverage on Linux/Python 3.11. Tests use temporary directories and mocks for external network and package-manager behavior; no internet or root is required, and the developer's real configuration is never read or written. See [docs/testing.md](docs/testing.md).

---

## 🛡️ Safety & Security

- **Scans are non-destructive** — file and security scans do not delete files. Package-manager commands may access their normal caches or logs.
- **Overwrite protection** — duplicates never auto-delete; backup restore requires `--force` to replace existing files. Workspace `--force` replaces template files.
- **No auto-install** — packages are only inspected, never installed/removed automatically.
- **Credential redaction** — URL userinfo, query values and common sensitive HTTP headers are masked in diagnostic output; review output before sharing because arbitrary secrets cannot be recognized reliably.
- **No root required** — works without elevated privileges; explains when info is limited.
- **Non-invasive security checks** — limited heuristics, not vulnerability verification. Network checks contact the user-specified host or the documented connectivity endpoints.
- **Backup restrictions** — source symlinks and special files, and archive links and special entries, are refused; creation streams data and publishes atomically, while restore verifies a private snapshot before writing. Restore journals replacements and rolls back when a member fails, but it is not crash-atomic and does not restore ownership, ACLs or timestamps. It is available only where the OS provides the required directory-relative, no-follow operations. See [backup safety](docs/backup-safety.md).
- **No telemetry** — ForgeKit sends no analytics, crash reports or update pings; it contacts only the hosts you ask it to, plus the documented connectivity endpoints. Details in [SECURITY.md](SECURITY.md).

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

```bash
git checkout -b feat/my-feature
# make changes + tests
ruff check src/ tests/ && ruff format --check src/ tests/ && pytest
git push && open PR
```

---

## 📝 License

MIT — see [LICENSE](LICENSE).

---

## 🙏 Acknowledgments

Built with [Typer](https://typer.tiangolo.com/), [Rich](https://github.com/Textualize/rich), [psutil](https://github.com/giampaolo/psutil), [Requests](https://requests.readthedocs.io/).

