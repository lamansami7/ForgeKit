# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.2.x   | ✅        |
| 0.1.x   | ⚠️ superseded — upgrade to 0.2.x |

## What ForgeKit's Security Features Do (and Don't)

- ForgeKit performs **non-invasive, read-only** diagnostics: file permissions, SSH config checks, world-writable detection, firewall presence, and update status.
- It does **not** perform exploitation, password cracking, intrusive vulnerability scanning, or stealth operations.
- It never claims a system is "secure" — findings are labeled `pass`/`warn`/`fail`/`info`.

## Reporting a Vulnerability

If you discover a security vulnerability in ForgeKit:

1. **Do not open a public issue.**
2. Use [GitHub private vulnerability reporting](https://github.com/lamansami7/ForgeKit/security/advisories/new) or email the maintainer at `lamansami7@gmail.com`.
3. Include steps to reproduce, impact, and suggested fix if available.

The maintainers will review reports and coordinate disclosure as capacity permits.

## Best Practices for Users

- Run `forge security` and `forge doctor` regularly.
- Keep your package manager updates current (`forge packages updates`).
- Never run ForgeKit (or any tool) as root unless specifically required.
- Review backup archives and use `--dry-run` before restoring. `--force` explicitly replaces existing regular files.
- Restore rejects links and special files. It journals every change and rolls back when a member fails, but it is not crash-atomic: a hard kill or power loss can leave a partial restore plus a `.forgekit-restore-*` directory. Test backups separately, keep a trusted SHA-256 digest, and read [backup safety](docs/backup-safety.md).
- Network timeouts do not impose a strict total deadline on DNS or slow headers. Redaction is best-effort; review output before sharing.
- These diagnostics cannot establish that a system or archive is secure.

## Data handled by ForgeKit

ForgeKit has **no telemetry, no analytics, no crash reporting and no update
pings**. It does not transmit data on its own. The only outbound traffic is what
you explicitly ask for:

| Action | Destination |
|--------|-------------|
| `forge net ping HOST` | the host you name (ICMP or TCP 80/443) |
| `forge net dns DOMAIN` | your system resolver |
| `forge net http URL` | the URL you name (TLS verification enabled, no body download) |
| `forge net check` | `1.1.1.1` and `google.com` over HTTPS plus the system resolver |
| `forge packages updates` / `forge security` | local package manager metadata only (no index refresh) |

Local data:

- Configuration: `$XDG_CONFIG_HOME/forgekit/config.toml` (mode 0600), never
  containing secrets by design.
- Optional cache/history helpers (`forgekit.storage`) write JSON and SQLite files
  under `$XDG_CACHE_HOME/forgekit` with private permissions. The CLI does **not**
  call them automatically, so normal usage writes no history and no cache.
- Backups, restores and workspace scaffolding write only where you point them.

Known exposure paths: diagnostic output includes hostnames, usernames, paths,
process names and interfaces, so redact before sharing. URL userinfo, query
strings, `Location` headers and common token headers are masked, but arbitrary
secrets in paths, file contents or commit messages are not detectable in general.
