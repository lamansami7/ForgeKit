# Commands Reference

## Global

- `forge` — overview + system summary
- `forge --help`, `forge --version`
- `forge --json` where applicable (structured JSON, no Rich markup)
- Commands normally return 0 on success, 1 for detected failures, and 2 for invalid CLI syntax. With an explicit `--json` flag, syntax and configuration errors are JSON too. If JSON is enabled only by configuration, errors before the configuration can be loaded (such as an unknown top-level option) are still rendered as text.

## System

- `forge system` — summary (OS, kernel, hostname, arch, uptime, CPU, memory, disk, Python, user)
- `forge system cpu [--json] [--per-core]` — model, cores, usage, per-core, frequency
- `forge system memory [--json]` — RAM + swap with thresholds
- `forge system disk [--json]` — partitions, mountpoints, filesystem, warnings
- `forge system processes [--limit N] [--sort cpu|memory] [--json]`

## Network (`forge net`)

- `forge net` — local interface and bound socket overview
- `forge net ping HOST [-c N] [-t TIMEOUT] [--json]`
- `forge net dns DOMAIN [--timeout N] [--json]` — resolution is bounded by a wall-clock timeout
- `forge net check [--json] [--timeout N]` — DNS + HTTPS checks
- `forge net ports [--json]` — listening TCP and bound UDP sockets, PID/process if permitted; results may be incomplete
- `forge net interfaces [--json]` — IP/MAC/MTU/stats
- `forge net http URL [--json] [--headers] [--timeout N]` — status, time, redirects, redacted headers

## Git

- `forge git [--path PATH] [--json]` — summary
- `forge git status [--path PATH] [--json]`
- `forge git history [--path PATH] [--limit N] [--json]`
- `forge git branches [--path PATH] [--json]`
- `forge git inspect TARGET [--path PATH] [--json]`

All Git commands are read-only.

## Files

- `forge files large PATH [--threshold MB] [--limit N] [--json]`
- `forge files search PATH QUERY [--ext] [--limit N] [--json]`
- `forge files size PATH [--json]` — breakdown + largest files
- `forge files empty PATH [--json]` — empty leaf directories, read-only
- `forge files duplicates PATH [--min-size BYTES] [--json]` — SHA256 hashing, groups

Filesystem scans exclude configured directory names, do not follow symlinks by default, and log inaccessible paths. `--limit` limits output, not necessarily traversal time.

## Packages

- `forge packages [--json]` — detect apt/dnf/yum/pacman/zypper/apk/brew
- `forge packages list [--manager NAME] [--limit N] [--json]` — apt, dnf, pacman or brew
- `forge packages updates [--manager NAME] [--json]` — based on locally cached apt, dnf or pacman metadata; may be stale
- `forge packages info [--json]`

ForgeKit never installs or removes packages automatically. Metadata checks do not refresh package indexes, so a zero count is not proof the system is up to date. Some package managers may maintain their usual logs.

## Developer

- `forge dev [--json]` — detect python/pip/git/node/npm/java/gcc/clang/docker/podman/rustc/cargo/go/php/ruby + PATH
- `forge dev check [--json]`
- `forge dev versions [--json]`

## Security

- `forge security [--path PATH] [--json]` — privilege, SSH perms, world-writable, firewall, updates, risky patterns
- `forge security check [--path PATH] [--json]`
- `forge security scan FILE [--json]` — hardcoded secrets, chmod 777, etc.

Non-invasive, no claims of "secure".

## Backup

- `forge backup create SOURCE [DEST] [--compression gz|bz2|xz|none] [--dry-run] [--json]`
- `forge backup list ARCHIVE [--json]`
- `forge backup verify ARCHIVE [--sha256 DIGEST] [--json]` — structural checks and optional trusted SHA-256 comparison
- `forge backup restore ARCHIVE DEST [--dry-run] [--force] [--json]` — overwrite protection, traversal-safe, journaled rollback

Source files are never deleted.

## Workspace

- `forge workspace create NAME [--template python|node|generic] [--path DIR] [--git] [--force] [--json]`
- `forge workspace templates [--json]`
- `forge workspace inspect PATH [--json]`

No npm/pip install is executed. Git init runs only with `--git` and requires an
available descriptor-backed path (`/proc/self/fd` or `/dev/fd`). Creation requires
POSIX directory-relative no-follow APIs; unsupported platforms fail closed. Template
files are written individually, so interruption or Git failure can leave a partial
project; there is no transactional rollback. `--force` permits replacing template
files in an existing project, so keep your own backup first.

## Doctor

- `forge doctor [--json] [--verbose]` — Python, install, deps, config, PATH, platform, permissions, optional tools

## Dashboard

- `forge dashboard [--refresh N] [--json]` — live Rich view on terminals, one snapshot when redirected; Ctrl+C exits

## Config

- `forge config show [--json] [--path PATH]`
- `forge config init [--force] [--path PATH] [--json]`
- `forge config validate [--json] [--path PATH]`
- `forge config get KEY [--path PATH] [--json]`
- `forge config set KEY VALUE [--path PATH] [--json]`
- `forge config path [--json]`

## Info

- `forge info [--json]`

### Backup safety and integrity

Creation streams files into a temporary archive and publishes it only after success;
it refuses an existing archive and destinations inside the source. Dry runs do not
create directories or files. Symlinks and special files in the source are rejected,
not skipped. Hard-linked source files are stored as independent regular files.

Restore rejects absolute paths, `..`, backslashes, colons, duplicate names, symbolic and hard
links, devices, and FIFOs. It refuses to follow existing symlinks even with `--force`.
An existing directory may be used; an existing regular file requires `--force`.
`--force` is explicit consent to replace conflicting files. Non-interactive restores
without conflicts do not prompt.

Restore is journaled rather than fully transactional. Each replaced file is renamed into a
private `.forgekit-restore-<random>` directory inside the destination before the new file is
published, and new files/directories are recorded. If any member fails (disk full, permission
error, I/O error, Ctrl+C), the journal is replayed in reverse so the destination returns to its
previous state; the command exits 1 with `rolled_back: true` (or `rolled_back: false` plus
`rollback_errors` when the undo itself failed). On success the journal is deleted because
replacing those files is the explicit effect of `--force`. A hard kill or power loss can still
leave the journal and a partial restore behind; inspect the destination and the journal before
retrying. Ownership, timestamps, ACLs, extended attributes and original directory modes are not
restored, and content is not `fsync`ed. Inspect the archive and test recovery in a separate
directory before relying on it. See [backup safety](backup-safety.md).

`verify` reads file contents and compressed streams, checks tar structure and rejects
unsafe members. A tar archive has no inherent per-file content checksums: save the
SHA-256 printed at creation in a trusted separate location and verify it later with
`forge backup verify ARCHIVE --sha256 DIGEST`. This compares bytes, not authenticity;
it is not a signature. It cannot prove that the source was unchanged while backed up.
Restore snapshots the compressed archive to a private temporary file before verifying
and extracting the exact same bytes. This needs free temporary space roughly equal
to the archive plus a 64 MiB reserve; set `TMPDIR` to a suitable private filesystem.
Dry runs do not create a snapshot or destination and do not verify file contents.
Restore refuses symlinks in destination ancestors as well as inside the destination.
Safe restore requires POSIX directory-relative and no-follow APIs and fails closed
when unavailable. Listing and verification remain available independently.

The implementation limits archives to 100,000 entries, 1 MiB per extended metadata
header, 4,096 path characters, 128 path components and 1 TiB of archive or expanded
data. Sparse members are rejected. Even below these limits, decompression may require
substantial CPU, time and disk; do not process untrusted archives without adequate
resource isolation. A concurrently changing source is not a consistent snapshot—use
a filesystem snapshot for important or active data.

### Diagnostics and verbosity

`--verbose`/`-v` sets the `forgekit` logger to DEBUG and writes diagnostics to stderr, so
stdout stays parseable as JSON. Log output never appears inside JSON documents.

### Network limitations

Ping uses ICMP when the system executable is available; otherwise it attempts TCP
connections on ports 80 and 443 and labels the result `tcp`. DNS resolution is provided
by the system resolver; ForgeKit bounds each lookup with a wall-clock timeout and reports
`DNS resolution timed out after Ns` instead of hanging, but the resolver call itself cannot
be cancelled. HTTP uses TLS verification,
per-socket timeouts, streaming responses and at most five redirects. These are not a
strict end-to-end deadline for DNS or a server slowly delivering headers. Displayed URL
userinfo and query values and common sensitive headers are redacted, but arbitrary
secrets in paths or other headers may remain. Review output before sharing.

Diagnostics are point-in-time observations, not complete inventories: processes and
mounts can disappear or be hidden by permissions. A CPU measurement blocks briefly;
fast-changing process CPU values and directory sizes are approximate. The security
permission scan skips links and common large directories, limits traversal, and
reports when results are incomplete. World-writable sticky directories are
informational rather than treated as proof of a vulnerability.
