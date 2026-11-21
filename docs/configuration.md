# Configuration

ForgeKit uses TOML at `$XDG_CONFIG_HOME/forgekit/config.toml` when XDG_CONFIG_HOME is absolute, otherwise `~/.config/forgekit/config.toml`. Use `forge --config /path/to/config.toml ...` to override it globally.

## Default Config

See `forge config show` or the file after `forge config init`:

```toml
[general]
output_format = "auto"
colors = true
log_level = "WARNING"

[dashboard]
refresh_interval = 2.0
show_network = true
show_processes = true

[thresholds]
cpu_warning = 80.0
memory_warning = 85.0
disk_warning = 85.0

[backup]
default_destination = "~/backups"
compression = "gz"

[files]
large_threshold_mb = 100
exclude_dirs = [".git", "__pycache__", ".venv", "venv", "node_modules", ".cache"]

[network]
ping_timeout = 5
http_timeout = 10
```

## Managing

```bash
forge config path
forge config show
forge config show --json
forge config init
forge config validate
forge config get dashboard.refresh_interval
forge config set thresholds.disk_warning 90
forge config set general.output_format json
forge config set files.exclude_dirs ".git,.venv,node_modules"
```

## Notes

- No secrets/passwords are stored. Do not add them.
- Validation rejects invalid values (e.g. refresh_interval out of 0.5–60).
- Use `--path /tmp/my.toml` on config subcommands that accept it, or global `--config /tmp/my.toml` on any command.
- A missing file uses defaults. Malformed, unreadable, unknown-key or invalid configuration is reported as an error. `doctor` and `config validate` can diagnose it.
- `config set` preserves comments, refuses unknown keys and symlink config files, and writes atomically with mode 0600 on POSIX. `config init --force` explicitly replaces the file.
- `general.output_format=json` enables JSON by default; `--json` overrides the default. `general.colors=false`, `general.output_format=plain`, `--no-color`, or `NO_COLOR` disables colors (plain retains table layout).
- The dashboard uses its refresh and visibility settings; file exclusions and size threshold, backup destination/compression, network timeouts, and system warning thresholds are configurable.
