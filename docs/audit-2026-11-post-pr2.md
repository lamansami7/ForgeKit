# Post-PR2 audit — 2026-11

This is the maintainer audit of ForgeKit after PR #2 was merged into `main`
(merge commit `0a60320`). It records what was verified, what was changed, what
remains limited, and the release level this state supports.

- Audit date: 2026-11-21
- Starting point: `main` at `0a60320` (PR #1 initial release, PR #2 hardening)
- Audited version: 0.1.0 → prepared as 0.2.0
- Environment used for verification: Debian 12 container, Linux 6.x, Python
  3.11.2, no root, no network access except a filtered proxy
- Method: read every module, then run the CLI, tests, coverage, lint, builds and
  clean installs. Claims below are backed by a command that was actually run.

## 1. Repository state

| Area | Verified state |
|------|----------------|
| Branch history | PR #1 (initial CLI) and PR #2 (hardening) are merged; no work-in-progress branches claimed as released |
| Tree | Clean, Hatchling build backend, `src/` layout, 13 command groups |
| Source size | ~6,400 lines in `src/forgekit` before removal of dead modules |
| Version | Single source in `src/forgekit/__init__.py`, read by Hatchling |
| Tests (start) | 234 passed, 79% statement coverage |
| Tests (end) | 396 passed, 91% statement coverage |
| Lint | `ruff check src/ tests/` and `ruff format --check src/ tests/` clean before and after |
| Packaging | Wheel and sdist both build, install in isolated venvs outside the repo, pass `pip check` and CLI smoke tests |

## 2. Command-by-command audit

Every command was exercised with and without `--json`, with valid, invalid and
failure inputs. Findings are grouped; "verified" means the behaviour was
observed in a real subprocess run.

### System — good
- Summary, CPU (including `--per-core`), memory/swap, disk and processes render
  correctly and return consistent JSON.
- Missing hardware and permissions are tolerated: `get_system_summary()` catches
  collector failures, disk has a container fallback, processes tolerate
  `AccessDenied`/`NoSuchProcess`/`ZombieProcess`, uptime/load/battery degrade to
  `null`.
- CPU sampling blocks for 250 ms (documented); process sampling also primes and
  waits 250 ms so the first reading is meaningful.

### Network — good, with documented limits and two fixes
- Ping resolves once, uses ICMP when a `ping` binary exists, and labels a TCP
  fallback as `method: "tcp"` instead of pretending it measured ICMP.
- **Fixed:** DNS resolution had no timeout for `ping`, `dns` and the DNS leg of
  `check`; a dead resolver could stall the command for the system resolver
  timeout. Resolution now runs in a daemon worker with a wall-clock bound and a
  clear `DNS resolution timed out after Ns` error.
- HTTP uses TLS verification, `stream=True`, no automatic redirects, at most five
  manual redirect hops, no body reads, rejects embedded credentials and invalid
  ports, and redacts userinfo, query strings, `Location`, and common sensitive
  headers.
- **Fixed:** header values had no display cap and the user agent was hardcoded to
  `ForgeKit/0.1.0`. Headers are now capped (100 entries, 1024 characters each)
  and the user agent follows the package version.
- `net ports` and `net interfaces` report permission problems as errors instead
  of empty success (verified by unit test with `psutil.AccessDenied`).

### Git — good
- All commands are read-only; `run_command` injects `--no-optional-locks` and
  `-c core.fsmonitor=false` for git, avoiding repository-configured hooks.
- Porcelain `-z` parsing preserves spaces and unusual names; renames consume the
  extra path entry.
- Remote URLs pass through `redact_url`, which masks userinfo and query values.
  Verified end-to-end with a remote URL containing a password and token.
- Redaction remains best-effort: a token embedded in a *path* is not masked, and
  commit messages/authors are shown verbatim. This is documented.

### Files — good
- Traversal uses `os.walk(followlinks=False)`, prunes configured exclusions,
  logs inaccessible paths, and skips non-regular entries for sizing and hashing.
- Large-file and duplicate scans keep bounded heaps/groups; hashing streams in
  1 MiB chunks. Directory size breakdown and empty-directory detection are
  read-only.
- Symlinks are neither followed nor counted. Race conditions (file replaced
  during scan) surface as logged warnings or are skipped, never as tracebacks.

### Packages — good
- Detection covers apt/dnf/yum/pacman/zypper/apk/brew; update checks use cached
  metadata only (`apt list --upgradable`, `dnf --cacheonly check-update`,
  `pacman -Qu`) and never refresh indexes.
- **Fixed:** detection re-ran up to seven `--version` subprocesses on every call
  (up to three times per command). It now probes once per process and can be
  refreshed explicitly.
- **Fixed:** `--manager` was annotated as `str` with a `None` default; corrected.
- Listing is read-only and limited to apt/dnf/pacman/brew. Unsupported managers,
  missing binaries, timeouts and non-zero exits produce explicit errors.

### Developer — good
- 15 tools probed by `shutil.which` with alternates (`python3`/`python`,
  `pip`/`pip3`); versions come from the tool itself, and failures are reported as
  "version unavailable" rather than a fabricated version.
- `java -version` falls back to the correct flag. PATH diagnostics detect empty
  PATH, duplicates, missing directories and common directories missing from PATH.

### Security — honest and non-invasive
- Privilege, SSH permissions (never reading key contents), bounded
  world-writable scan, firewall observation (ufw/firewalld/iptables), cached
  update status and an explicit-file risky-pattern scan.
- Wording never claims a system is secure; sticky world-writable directories are
  informational; incomplete scans are labelled as such.
- `security scan` refuses files over 1 MiB and non-regular files, and reports
  findings without echoing the matched secret value.

### Backup — heavily audited; one substantial improvement
Creation already streamed into a temporary file, published with an atomic hard
link, rejected existing archives and destinations inside the source, and refused
symlinks/special files in the source. Verification reads every member, checks
compression trailers, rejects traversal, absolute paths, drive letters,
backslashes, duplicates, links, devices, FIFOs, sparse members and metadata
bombs, and enforces 100,000 members / 1 MiB metadata / 4,096-char paths / 128
components / 1 TiB.

**The verified gap was partial restoration.** Earlier code extracted members
directly into the destination and documented that a mid-restore failure could
leave earlier files restored. The audit found this to be reachable (disk full,
permission change, I/O error, interrupt). See section 3 for the fix.

Remaining backup limitations are listed in section 7 and in
[backup safety](backup-safety.md).

### Workspace — good
- Templates are generated in memory, validated in a full preflight, and written
  through pinned directory descriptors with `O_NOFOLLOW`, `O_EXCL` and atomic
  publication. Symlinked destinations or any symlink inside the project tree are
  refused. Existing files require `--force`, and `--force` still refuses to
  replace links or non-regular files. Concurrent creation cannot be overwritten.
- Git initialization only runs with `--git`, needs a descriptor-backed path
  (`/proc/self/fd` or `/dev/fd`), and a failure is reported without deleting the
  generated files. Creation is not transactional (documented): an interrupt can
  leave a partial project.

### Doctor — good
- Nine checks (Python, install metadata, dependencies, configuration, PATH,
  platform, privileges, optional tools, config file) with actionable `fix` text,
  JSON output identical in shape, and a non-zero exit only for real failures.
- Platform messages call macOS/Windows experimental rather than supported.
- **Improved:** the invalid-configuration path now returns a clear, JSON-readable
  failure instead of an early abort.

### Dashboard — good
- Non-TTY output renders one snapshot and exits instead of looping forever.
- Live mode uses a Rich `Live` context manager, so the terminal is restored on
  Ctrl+C; the interrupt path prints a clean exit message (tested).
- Refresh values are validated (finite, 0.5–60) including values coming from
  configuration. Dead code in the view builder was removed.

### Configuration — good, one UX fix
- Strict types, unknown keys and range checks; missing file means defaults;
  malformed TOML, unreadable files and symlinked config paths are errors.
- Writes use a temporary file, `fsync`, and atomic publication (hard link for
  create, `os.replace` for update) with mode 0600 on POSIX; `config set`
  preserves comments and refuses unknown keys.
- **Fixed:** `config init` on an existing file leaked a raw hard-link `OSError`
  (`[Errno 1] Failed to create hard link ...`) instead of a clear message. It now
  reports `Configuration already exists: <path>; pass --force to replace it`,
  while still relying on the hard link to win races.

## 3. Restore transactionality (dedicated investigation)

**Question:** can restore be made transactional without weakening existing
protections?

**Conclusion:** a fully transactional filesystem restore is not achievable
portably (there is no portable atomic multi-file commit), but a journaled
restore with best-effort rollback is feasible and was implemented.

What changed:

- Restore extracts into the destination while recording every mutation in a
  private `.forgekit-restore-<random>` directory inside the destination root:
  - existing regular files replaced under `--force` are renamed (not deleted)
    into the journal before the new file is published, so the original bytes and
    metadata are preserved with no extra disk space;
  - newly created files and directories are recorded, including destination
    ancestors this restore created.
- If any member fails (disk full, permission error, I/O error, interrupt), the
  journal is replayed in reverse: new files are unlinked, originals are renamed
  back, and created directories are removed. The command then reports
  `rolled_back: true` plus any rollback errors and exits 1.
- If the rollback itself cannot complete, ForgeKit does **not** pretend it
  succeeded: it reports `rolled_back: false`, lists the problems, and tells the
  user to inspect the destination.
- On success the journal is deleted: replacing files is the explicit effect of
  `--force`.

Guarantees and limits:

- Not covered: SIGKILL/power loss (a journal directory and partially restored
  files can remain), durability (`fsync` of restored content and directories is
  not performed), and metadata (ownership, ACLs, xattrs, timestamps, directory
  modes) are still not restored.
- The journal lives inside the destination root; it requires the same filesystem
  and the POSIX directory-relative/no-follow primitives the restore already
  required.
- Rollback is best-effort by design: it never deletes data it does not own, and
  it never silently reports success.

Ten new tests cover rollback of created files/directories, restoration of
overwritten originals including mode, honest reporting of incomplete rollback,
interrupt handling, JSON and text output, and a full nested round trip.

## 4. JSON and error-handling matrix

A scripted matrix ran 48 command forms in a subprocess (`--json` at root) and
parsed every stdout payload:

- All supported commands returned a single valid JSON document; no Rich markup,
  banners or log lines appeared on stdout.
- Failures (`exit 1`) returned `{"error": ...}` or a domain payload with an
  `error` field; parser/usage errors (`exit 2`) returned `{"error": ...}` when
  `--json` was explicit, and plain usage text otherwise.
- `config path` does not accept `--path` (by design, it reports the effective
  path); this was confirmed against the documented interface.
- Logging goes to stderr, so `--verbose` cannot corrupt JSON.

Documented exceptions: JSON enabled *only* by configuration cannot cover errors
raised before the configuration file is read (for example an unknown top-level
option). This remains documented in `docs/commands.md`.

## 5. Security and privacy audit

- No shell execution anywhere: every subprocess uses an argument list via
  `subprocess.run`. Git invocations are additionally hardened.
- No telemetry, analytics, crash reporting or background network activity. The
  only outbound requests are the ones a user invokes: `net ping`, `net dns`,
  `net check` (Cloudflare/Google endpoints), `net http <URL>`, plus package
  manager metadata reads that stay local. Verified by reading every call site.
- File writes are limited to: the archive and manifest output of `backup create`,
  restore output, workspace scaffolding, config files, and the opt-in
  cache/history helpers (which the CLI never calls automatically).
- The cache hashes keys and refuses symlinks; history refuses symlinked
  databases and creates files 0600. Neither is wired into the CLI.
- Sensitive output: URL userinfo/query, `Location` headers and common token
  headers are masked. Redaction is explicitly best-effort and documented as such.
- Archive handling fails closed on unsafe members and is bounded in members,
  metadata size, path depth, total expanded size and sparse members.
- Remaining limitations are documented in SECURITY.md rather than described as
  solved.

## 6. Performance and reliability (measured)

Measured as wall-clock time of the installed console script in a subprocess
(Debian 12 container, warm cache, single core):

| Command | Time | Peak child RSS |
|---------|------|----------------|
| `forge --version` | 248 ms | 36 MB |
| `forge system memory` | 261 ms | 44 MB |
| `forge system cpu` | 521 ms | 44 MB |
| `forge system processes --limit 5` | 540 ms | 45 MB |
| `forge doctor` | 278 ms | 45 MB |
| `forge dev` | 576 ms | 58 MB |
| `forge packages` | 271 ms | 58 MB |
| `forge files size src` | 265 ms | 58 MB |
| `forge security --path /tmp` | 320 ms | 58 MB |
| `forge backup create --dry-run src ...` | 287 ms | 58 MB |

- Import time is ~200 ms (Typer, Rich, psutil, requests); that is the floor for
  every invocation. `-X importtime` shows `requests` at ~43 ms of that; it was
  left in place because lazily importing it would weaken the test seam that mocks
  HTTP without complicating the module further.
- `system cpu` and `system processes` each include a deliberate 250 ms sample so
  the first reading is meaningful. `--per-core` adds a second 250 ms sample.
- `dev` runs up to 15 short `--version` subprocesses; package detection is capped
  at 7 and now runs once per process.
- Security collection is bounded (1,000 entries, home scan depth 3), filesystem
  scans stream in 1 MiB chunks, duplicate hashing runs only on same-size groups,
  and backup creation/verification stream rather than buffering.
- The dashboard refreshes with `Live` and never reads response bodies for HTTP.

Reliability checks: no command crashed when hardware data, permissions or
binaries were missing; failures were reported with exit 1 and actionable text;
JSON stayed parseable in every failure mode tested.

## 7. Tooling verification

```
ruff check src/ tests/            → All checks passed
ruff format --check src/ tests/   → 74 files already formatted
pytest                            → 396 passed
pytest --cov=forgekit             → 91% statements (gate: 90%)
python -m build                   → wheel + sdist built
clean venv: pip install dist/*.whl && pip check → no broken requirements
clean venv: pip install dist/*.tar.gz && pip check → no broken requirements
wheel/sdist: forge --version / --help / doctor / JSON commands → OK
```

Coverage by area (after this audit): commands 86–100%, services 84–96%, models
100%, storage 88–100%, core 88%. Uncovered lines are dominated by
platform-specific branches (Windows/Darwin paths), `__main__`, and defensive
`except` handlers that cannot be triggered without simulating OS failures.
Reaching 90% was realistic; a further rise would mostly add artificial tests.

## 8. Known limitations (unchanged or newly documented)

1. Backup creation is not a filesystem-consistent snapshot of an actively
   changing source; use an LVM/ZFS/btrfs snapshot for live data.
2. Restore does not preserve ownership, ACLs, xattrs, timestamps or directory
   modes, and is not crash-atomic (see section 3).
3. Archive SHA-256 proves integrity against a trusted value you stored
   separately; it is not a signature and cannot prove authenticity.
4. DNS uses the system resolver; the timeout is a wall-clock bound on the call,
   not a promise that the resolver thread has stopped.
5. HTTP timeouts are per socket operation, not an end-to-end deadline for slow
   header delivery.
6. Redaction cannot recognise arbitrary secrets in URL paths or unrelated
   headers.
7. Security and filesystem diagnostics are bounded heuristics, reported as such.
8. macOS and Windows remain unvalidated; POSIX-dependent features (safe restore,
   workspace creation) fail closed elsewhere. See
   [platform support](platform-support.md).
9. Python 3.12 and 3.13 are exercised only by CI, not in this local audit.
10. Only apt-based update/listing behaviour was exercised against a real package
    manager; dnf/pacman/zypper/apk/brew paths are covered by mocked tests.
11. No fuzzing/property-based testing, no root-privilege test matrix, and no
    independent third-party security review.

## 9. Release readiness decision

**Level: public alpha, prepared as 0.2.0.** Not a beta, not production-ready.

Why alpha is responsible now:

- Test suite is meaningful (396 tests, 91% coverage), lint/format clean, both
  distributions install and run outside the repository.
- All documented safety properties were verified by execution, and the backup
  restore path gained real rollback protection instead of only documentation.
- Limitations are documented honestly and no claim of full security or
  cross-platform support is made.

Why not beta or 1.0 yet:

- No validation on distributions other than Debian-derived Linux, and nothing at
  all on macOS/Windows.
- Backup/restore deserves an independent review before users rely on it.
- No external user feedback at this stage; the CLI surface may still change.

Conditions for a `0.2.0` publication (maintainer actions):

1. CI green on Python 3.11, 3.12 and 3.13 (the workflow exists; this audit only
   ran 3.11 locally).
2. Tag `v0.2.0`, build from a clean checkout, publish wheel + sdist, and verify
   `pip install forgekit==0.2.0` in an empty environment.
3. Confirm GitHub private vulnerability reporting is enabled and the contact in
   SECURITY.md is current.
4. Keep the "alpha" classifier and the platform/safety wording until macOS,
   Windows and additional distributions are validated.

Beta would additionally require: external testers on at least two non-Debian
distributions, an independent review of `backup_service.py`, and observed green
runs of the experimental platform workflow.
