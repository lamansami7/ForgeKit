# Changelog

All notable changes to ForgeKit will be documented here.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning.

## [0.1.0] - 2026-11-21

### Added
- Initial release of ForgeKit
- CLI `forge` with modular subcommands:
  - `forge system` — cpu, memory, disk, processes
  - `forge net` — ping, dns, check, ports, interfaces, http
  - `forge git` — status, history, branches, inspect
  - `forge files` — large, search, size, empty, duplicates
  - `forge packages` — manager detection, updates, list
  - `forge dev` — tool detection, PATH diagnostics
  - `forge security` — non-invasive checks, config scan
  - `forge backup` — create, list, verify, restore with safety
  - `forge workspace` — python/node/generic scaffolding
  - `forge doctor` — self-diagnostics
  - `forge dashboard` — live Rich dashboard
  - `forge config` — TOML config management
  - `forge info` — about
- Rich terminal output + `--json` across commands
- Configuration at `~/.config/forgekit/config.toml`
- CI workflow (ruff + pytest + packaging)
- Comprehensive pytest suite
- Documentation in `docs/`
