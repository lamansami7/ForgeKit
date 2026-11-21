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
2. Email the maintainer or use GitHub's private vulnerability reporting.
3. Include steps to reproduce, impact, and suggested fix if available.

We aim to respond within 72 hours and will coordinate disclosure.

## Best Practices for Users

- Run `forge security` and `forge doctor` regularly.
- Keep your package manager updates current (`forge packages updates`).
- Never run ForgeKit (or any tool) as root unless specifically required.
- Review backup archives before restoring with `--force`.
