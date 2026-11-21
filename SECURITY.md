# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |

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
- Restore rejects links and special files and is not transactional. Test backups separately, keep a trusted SHA-256 digest, and read [backup safety](docs/commands.md#backup-safety-and-integrity).
- Network timeouts do not impose a strict total deadline on DNS or slow headers. Redaction is best-effort; review output before sharing.
- These diagnostics cannot establish that a system or archive is secure.
