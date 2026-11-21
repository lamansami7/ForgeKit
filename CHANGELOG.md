# Changelog

All notable changes to ForgeKit will be documented here.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning.

## [Unreleased]

Nothing yet.

## [0.2.0] - 2026-11-21

Post-PR2 audit release: hardening from PR #2 plus the gaps found by the
2026-11 audit. See [docs/audit-2026-11-post-pr2.md](docs/audit-2026-11-post-pr2.md).

### Added
- Journaled backup restore: files replaced under `--force` are renamed into a
  private `.forgekit-restore-*` directory inside the destination and moved back if
  any member fails; newly created files and directories are removed on failure.
  Failures report `rolled_back`/`rollback_errors` (JSON) or a clear message and
  never claim an undo that did not happen. Successful restores report an
  `overwritten` count.
- Bounded DNS resolution for `net ping`, `net dns` and `net check`, a `--timeout`
  option on `net dns`, and an explicit timeout error instead of a resolver hang.
- Verbose mode (`--verbose`/`-v`) now configures logging (stderr only).
- Safer opt-in cache/history helpers with private files and no automatic command
  recording; the CLI still never uses them implicitly.
- JSON-formatted argument errors when `--json` is explicit; restore snapshots and
  archive resource limits.
- Regression tests for malicious archives, overwrite/symlink safety, invalid
  configuration, diagnostics and templates, plus new behaviour-focused suites for
  text output, command error paths and restore rollback (234 → 396 tests, 79% → 91%
  coverage).
- `docs/backup-safety.md`, `docs/platform-support.md`, `docs/testing.md`,
  `docs/release-procedure.md`, the post-PR2 audit report, an experimental
  non-blocking macOS workflow and Dependabot configuration.
- CI: sdist smoke test, backup create/verify/restore round trip, and a coverage
  gate (`fail_under = 90`).

### Changed
- Reject unsafe archive paths, links and special files; refuse symlinked source
  entries; protect existing files during restore and workspace creation.
- Stream backup contents, publish archives atomically, verify compressed streams
  and optionally compare a trusted SHA-256 checksum.
- Restore no longer overwrites existing files without preserving them first.
- Preserve and validate TOML configuration, refuse symlink configuration files and
  write changes atomically.
- `config init` on an existing file reports "Configuration already exists … pass
  `--force`" instead of leaking a raw hard-link `OSError`.
- Redact URL userinfo/query values and common sensitive headers, restrict HTTP
  redirects, avoid reading response bodies, cap displayed headers and derive the
  user agent from the package version.
- Make global JSON and configuration options effective, report more failures with
  nonzero exit codes, and avoid indefinite dashboards when output is redirected.
- Correct process CPU sampling, memory accounting, disk fallback, filesystem size
  breakdowns, Git pathname handling and UDP socket reporting.
- Use cached metadata for package update checks, probe package managers once per
  process, and clarify platform, network, backup and diagnostic limitations.
- Derive package metadata and CLI version from one version source; use an SPDX
  license expression and ship the LICENSE file in the wheel.
- Test built wheels and sdists separately in CI.

### Removed
- Dead re-export command stubs (`commands/cpu.py`, `disk.py`, `dns.py`,
  `memory.py`, `ports.py`, `processes.py`), unused `core/checks.py`,
  `core/environment.py`, `core/runner.py`, `models/diagnostic.py`, unused output
  helpers and dead dashboard code.

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
