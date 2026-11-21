# Release checklist

ForgeKit is pre-1.0. This is a checklist, not a claim of release readiness.
Items are ticked **only** when the command was actually run and observed on a
specific environment; the environment and date are recorded next to it. See
[release procedure](release-procedure.md) for the full sequence and
[the post-PR2 audit](audit-2026-11-post-pr2.md) for the evidence behind this list.

## Verified for the 0.2.0 preparation (Linux/Debian 12, Python 3.11.2, 2026-11-21)

- [x] `ruff check src/ tests/` — clean.
- [x] `ruff format --check src/ tests/` — clean.
- [x] `pytest` — 396 passed, no network and no root required.
- [x] `pytest --cov=forgekit --cov-report=term-missing` — 91% statements, gate at 90%.
- [x] `python -m build` — wheel and sdist built from the same source tree.
- [x] Wheel installed in a clean virtualenv outside the repository; `pip check`,
      `forge --help`, `forge --version`, `forge doctor`, `forge system memory --json`
      (valid JSON) all pass.
- [x] sdist installed in a separate clean virtualenv; `pip check`, `forge --version`,
      `forge doctor`, JSON output and `forge backup create --json` pass.
- [x] CLI JSON matrix: 48 command forms run as real subprocesses; every document
      parsed as JSON, no markup/banner/log contamination on stdout.
- [x] Backup create/list/verify/restore exercised, including corrupt archives,
      traversal/absolute/symlink members, conflicts without `--force`, rollback of
      created and overwritten files, and simulated mid-restore I/O failure.
- [x] Configuration: invalid TOML, unknown keys, wrong types, symlinked config
      files, `config init` collision, atomic write and 0600 permissions exercised.
- [x] Workspace creation: existing destination, `--force`, symlink destination,
      invalid names, `--git`, and path-safety preflight exercised.
- [x] Version derives from one source (`src/forgekit/__init__.py`), and package
      metadata builds with an SPDX license expression and bundled LICENSE.
- [x] Documentation reviewed for claims about platforms, security, backup safety
      and telemetry; limitations documented in `SECURITY.md`,
      `docs/backup-safety.md` and `docs/platform-support.md`.
- [x] Changelog updated for 0.2.0; release level decided (public alpha).

## Verified in CI (Linux, 2026-11-21, run 44947121842 on PR #3)

- [x] CI green on Python 3.11 (1m10s), 3.12 (1m32s) and 3.13 (1m17s).
- [x] Wheel smoke test, sdist smoke test and backup create/verify/restore round
      trip all ran and passed inside those jobs.

## Not yet verified — required before publishing or claiming more support

- [ ] `Platforms (experimental)` macOS workflow completed. It was started but had
      not been allocated a runner within the audit window (status: queued). It is
      non-blocking and does **not** imply macOS support.
- [ ] Real package-manager behaviour verified beyond apt (dnf, pacman, zypper, apk,
      brew) on real systems. Current coverage there is mocked.
- [ ] Independent review of `services/backup_service.py` (creation, verification,
      journal, rollback) by someone other than the author.
- [ ] Restore tested on non-ext4 filesystems (xfs, btrfs, ZFS, exFAT) to confirm
      rollback behaviour with different rename/link semantics.
- [ ] Test on a second Linux distribution family (Fedora/Arch/Alpine) with a real
      user account and a home directory containing real dotfiles.
- [ ] macOS and Windows status reviewed; only claim support after running the full
      suite and every command on those platforms.
- [ ] PyPI project name reserved and a token stored outside the repository; test
      upload to TestPyPI performed.
- [ ] GitHub private vulnerability reporting confirmed enabled and the contact in
      `SECURITY.md` confirmed current.
- [ ] Release notes reviewed for honest wording (alpha, no production-readiness or
      "secure system" claims), and the tagged commit rebuilt from a clean checkout.

## Decision

Do not call this 1.0. Do not describe it as production-ready, as a security
assessment, or as macOS/Windows-supported. A public **0.2.0 alpha** is appropriate
once the CI items above have been observed; a beta additionally requires external
testing and an independent backup review.
