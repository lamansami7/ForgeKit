# Troubleshooting

## forge not found
- Ensure pip bin is in PATH: `echo $PATH`, add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc`
- Reinstall: `pip install -e .`

## Permission denied on ports/processes
- Some port PID/process info requires additional permissions. ForgeKit reports inaccessible information or an error rather than inventing values.
- Do not run whole tool as root; use targeted sudo only if needed.

## DNS or ping fails
- Check internet: `forge net check`
- DNS: try `forge net dns localhost` (should resolve)
- Firewall may block ICMP. Only when the ping executable is unavailable, ForgeKit attempts TCP ports 80/443 and labels the method `tcp`; TCP failure does not prove a host is down.

## Git commands say "Not a git repository"
- Run inside repo or pass `--path /path/to/repo`

## Files scan slow or permission errors
- Large trees take time. `--limit` limits output, not the work needed to find the largest files.
- Permission errors are logged and skipped, not fatal.
- Exclude dirs via config: `files.exclude_dirs`

## Backup restore refuses to overwrite
- Use `--dry-run` to preview, `--force` to confirm overwrite.
- Unsafe paths, symlinks, hard links and special archive entries are rejected. Restore requires POSIX no-follow, directory-relative filesystem operations; it is not available on every platform.

## Dashboard flicker or high CPU
- Increase refresh: `forge dashboard --refresh 3`
- Set in config: `forge config set dashboard.refresh_interval 3.0`

## Config invalid
- `forge config validate` shows errors
- Back up or edit the file before resetting it with `forge config init --force` (which replaces it).

## Still stuck?
- `forge doctor --verbose` — shows environment diagnostics
- Open an issue with `forge doctor` output and steps to reproduce.
