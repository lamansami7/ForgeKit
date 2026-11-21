# Platform support

ForgeKit is **Linux-first**. Every feature listed as validated was exercised on
Linux (Debian 12, Python 3.11) during the 2026-11 audit. Nothing in this project
has been validated on macOS or Windows, and no support is implied by a command
existing there.

| Capability | Linux | macOS | Windows |
|------------|-------|-------|---------|
| Install from wheel/sdist | ✅ validated | ⚠️ untested | ⚠️ untested |
| System CPU / memory / disk / processes | ✅ validated | ⚠️ untested (psutil) | ⚠️ untested (psutil) |
| Network ping / dns / http / ports / interfaces | ✅ validated | ⚠️ untested | ⚠️ untested |
| Git commands | ✅ validated | ⚠️ untested | ⚠️ untested |
| Filesystem scans | ✅ validated | ⚠️ untested | ⚠️ untested |
| Package detection | ✅ apt validated; dnf/pacman/zypper/apk/brew mocked | ⚠️ brew mocked only | ❌ no supported manager |
| Developer tool detection | ✅ validated | ⚠️ untested | ⚠️ untested |
| Security checks | ✅ validated | ⚠️ partial (no ufw/firewalld) | ❌ firewall checks unavailable |
| Backup create / list / verify | ✅ validated | ⚠️ untested | ⚠️ untested |
| Backup **restore** | ✅ validated | ⚠️ requires POSIX dir_fd APIs | ❌ fails closed |
| Workspace creation | ✅ validated | ⚠️ requires POSIX dir_fd APIs | ❌ fails closed |
| Dashboard (live) | ✅ validated | ⚠️ untested | ⚠️ untested |
| Configuration (TOML, atomic writes) | ✅ validated | ⚠️ untested | ⚠️ untested |

Legend: ✅ verified by execution · ⚠️ code exists but is not validated · ❌ not
available by design.

## Why some features fail closed

Safe restore and workspace creation depend on `os.open(..., dir_fd=...)`,
`O_NOFOLLOW`, `O_DIRECTORY`, `os.link(..., follow_symlinks=False)` and
`os.rename(..., src_dir_fd=...)`. Without them, a malicious or accidental symlink
swap in the destination cannot be prevented, so ForgeKit refuses to write instead
of falling back to unsafe path handling. Listing, verification, dry runs and
non-writing diagnostics remain available everywhere.

## Checking the current machine

```bash
forge doctor --json          # platform, permissions, optional tools
python -c "import os; print(sorted(os.supports_dir_fd, key=str))"
```

`forge doctor` reports macOS and Windows as experimental rather than supported.

## How macOS or Windows support could be validated

1. Run the full test suite on the target (`pytest -q`) and fix platform-specific
   failures instead of skipping them.
2. Run every command against real hardware: `system`, `net`, `git`, `files`,
   `packages`, `dev`, `security`, `backup`, `workspace`, `doctor`, `dashboard`.
3. Exercise restore and workspace creation, including symlink and permission
   cases, on the target filesystem (APFS, NTFS) and record the results.
4. Make `platforms.yml` blocking in CI only after it has been green repeatedly.
5. Update this table and the classifiers in `pyproject.toml` in the same change.

Until then, the `Operating System :: POSIX :: Linux` classifier and the platform
warnings in `forge doctor` stay in place.
