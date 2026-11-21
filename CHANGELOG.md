# Changelog

All notable changes to ForgeKit will be documented here.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning.

## [Unreleased]

### Security and safety
- Reject unsafe archive paths, links, special files and symlink traversal; protect existing files during restore and workspace creation.
- Stream backup contents, publish archives atomically, verify compressed streams, and optionally compare a trusted SHA-256 checksum.
- Preserve and validate TOML configuration, refuse symlink configuration files and write changes atomically.
- Redact URL userinfo/query values and common sensitive headers, restrict HTTP redirects, and avoid reading response bodies.

### Changed
- Make global JSON and configuration options effective, report more failures with nonzero exit codes, and avoid indefinite dashboards when output is redirected.
- Correct process CPU sampling, memory accounting, disk fallback, filesystem size breakdowns, Git pathname handling and UDP socket reporting.
- Use cached metadata for supported package update checks and clarify platform, network, backup and diagnostic limitations.
- Derive package metadata and CLI version from a single version source; test built wheels separately in CI.

### Added
- Regression tests covering malicious archives, overwrite and symlink safety, invalid configuration, diagnostics and template behavior.
- Release checklist and updated contributor/security documentation.
- Safer opt-in cache/history helpers with private files and no automatic command recording.
- JSON-formatted syntax errors with explicit `--json`; restore snapshots and resource limits.

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
- Rich terminal output and JSON for many commands
- Configuration at `~/.config/forgekit/config.toml`
- CI workflow (ruff + pytest + packaging)
- Initial pytest suite
- Documentation in `docs/`
