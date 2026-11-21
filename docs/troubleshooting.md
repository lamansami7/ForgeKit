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

## Restore failed and I do not know the destination state
- Read the error: `rolled_back: true` means the destination was returned to its previous state; `rolled_back: false` means some items could not be undone and the message lists which ones.
- If the process was killed (SIGKILL) or the machine lost power, look for `.forgekit-restore-<random>` in the destination root. It holds the original files that were being replaced; rename them back if you prefer the originals.
- Verify the archive again before retrying: `forge backup verify ARCHIVE --sha256 DIGEST`.
- See [backup safety](backup-safety.md) for the full recovery procedure.

## `forge config init` says the configuration already exists
- It never overwrites silently. Inspect the file with `forge config show`, then either edit it or run `forge config init --force` explicitly.

## A command succeeds but I expected diagnostics on stdout
- `--verbose`/`-v` logs to stderr by design so JSON on stdout stays valid. Redirect if needed: `forge --verbose system 2>debug.log`.
- Pipeline JSON is unchanged by logging; if you see log text mixed into JSON, that is a bug — please report it.

## Dashboard flicker or high CPU
- Increase refresh: `forge dashboard --refresh 3`
- Set in config: `forge config set dashboard.refresh_interval 3.0`

## Config invalid
- `forge config validate` shows errors
- Back up or edit the file before resetting it with `forge config init --force` (which replaces it).

## Still stuck?
- `forge doctor --verbose` — shows environment diagnostics
- Open an issue with `forge doctor` output and steps to reproduce.
