# Troubleshooting

## forge not found
- Ensure pip bin is in PATH: `echo $PATH`, add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc`
- Reinstall: `pip install -e .`

## Permission denied on ports/processes
- Some port PID/process info requires elevated privileges — ForgeKit reports "no permission" rather than failing.
- Do not run whole tool as root; use targeted sudo only if needed.

## DNS or ping fails
- Check internet: `forge net check`
- DNS: try `forge net dns localhost` (should resolve)
- Firewall may block ICMP — ForgeKit falls back to TCP.

## Git commands say "Not a git repository"
- Run inside repo or pass `--path /path/to/repo`

## Files scan slow or permission errors
- Large trees take time — use `--limit`
- Permission errors are logged and skipped, not fatal.
- Exclude dirs via config: `files.exclude_dirs`

## Backup restore refuses to overwrite
- Use `--dry-run` to preview, `--force` to confirm overwrite.
- Path traversal entries are blocked for safety.

## Dashboard flicker or high CPU
- Increase refresh: `forge dashboard --refresh 3`
- Set in config: `forge config set dashboard.refresh_interval 3.0`

## Config invalid
- `forge config validate` shows errors
- Reset: `forge config init --force`

## Still stuck?
- `forge doctor --verbose` — shows environment diagnostics
- Open an issue with `forge doctor` output and steps to reproduce.
