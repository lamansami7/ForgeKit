# Commands Reference

## Global

- `forge` — overview + system summary
- `forge --help`, `forge --version`
- `forge --json` where applicable (structured JSON, no Rich markup)
- All commands return 0 on success, 1 on failure.

## System

- `forge system` — summary (OS, kernel, hostname, arch, uptime, CPU, memory, disk, Python, user)
- `forge system cpu [--json] [--per-core]` — model, cores, usage, per-core, frequency
- `forge system memory [--json]` — RAM + swap with thresholds
- `forge system disk [--json]` — partitions, mountpoints, filesystem, warnings
- `forge system processes [--limit N] [--sort cpu|memory] [--json]`

## Network (`forge net`)

- `forge net ping HOST [-c N] [-t TIMEOUT] [--json]`
- `forge net dns DOMAIN [--json]`
- `forge net check [--json] [--timeout N]` — DNS + HTTPS checks
- `forge net ports [--json]` — listening sockets, PID/process if permitted
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

All filesystem scans exclude `.git/__pycache__/.venv/node_modules` by default (configurable) and avoid symlink loops.

## Packages

- `forge packages [--json]` — detect apt/dnf/yum/pacman/zypper/apk/brew
- `forge packages list [--manager NAME] [--limit N] [--json]`
- `forge packages updates [--manager NAME] [--json]` — read-only
- `forge packages info [--json]`

Never installs/removes automatically.

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

- `forge backup create SOURCE DEST [--compression gz|bz2|xz|none] [--dry-run] [--json]`
- `forge backup list ARCHIVE [--json]`
- `forge backup verify ARCHIVE [--json]` — tar integrity + sha256
- `forge backup restore ARCHIVE DEST [--dry-run] [--force] [--json]` — overwrite protection, traversal-safe

Source files are never deleted.

## Workspace

- `forge workspace create NAME [--template python|node|generic] [--path DIR] [--git] [--force] [--json]`
- `forge workspace templates [--json]`
- `forge workspace inspect PATH [--json]`

No npm/pip install is executed. Git init only with `--git`.

## Doctor

- `forge doctor [--json] [--verbose]` — Python, install, deps, config, PATH, platform, permissions, optional tools

## Dashboard

- `forge dashboard [--refresh N] [--json]` — live Rich view, Ctrl+C to exit

## Config

- `forge config show [--json] [--path PATH]`
- `forge config init [--force] [--path PATH]`
- `forge config validate [--json] [--path PATH]`
- `forge config get KEY [--path PATH]`
- `forge config set KEY VALUE [--path PATH]`
- `forge config path`

## Info

- `forge info [--json]`
