# Configuration

ForgeKit uses TOML at `~/.config/forgekit/config.toml` (XDG standard).

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
- Custom path: `--path /tmp/my.toml` with any config subcommand.
- Fallback to defaults if file missing or unreadable.
