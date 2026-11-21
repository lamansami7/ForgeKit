# Examples

## System

```bash
forge system --json | jq .cpu.usage_percent
forge system cpu --per-core
forge system memory
forge system disk
forge system processes --sort memory --limit 10
```

## Network

```bash
forge net ping 1.1.1.1 -c 3
forge net ping google.com --json | jq .avg_ms
forge net dns example.com
forge net check
forge net ports
forge net interfaces --json | jq '.[].name'
forge net http https://httpbin.org/status/200 --headers
```

## Git

```bash
git status # traditional
forge git  # richer summary
forge git history --limit 20 --json
forge git branches
forge git inspect src/forgekit/cli.py
```

## Files

```bash
forge files large ~/Downloads --threshold 200
forge files search ~/projects "config" --limit 20
forge files search ~/projects ".py" --ext
forge files size ~/projects --json | jq .total_size
forge files empty /tmp
forge files duplicates ~/Documents --json > dups.json
```

## Packages

```bash
forge packages
forge packages updates
forge packages list --manager apt --limit 30
```

## Developer

```bash
forge dev
forge dev versions
forge dev check --json
```

## Security

```bash
forge security
forge security --path ~/myproject
forge security scan ./nginx.conf
```

## Backup

```bash
mkdir -p ~/backups
forge backup create ./src ~/backups --dry-run
forge backup create ./src ~/backups
forge backup list ~/backups/src-*.tar.gz
forge backup verify ~/backups/src-*.tar.gz
mkdir /tmp/restore && forge backup restore ~/backups/src-*.tar.gz /tmp/restore --dry-run
forge backup restore ~/backups/src-*.tar.gz /tmp/restore --force
```

## Workspace

```bash
forge workspace templates
forge workspace create myapp --template python --path ~/projects --git
forge workspace inspect ~/projects/myapp --json
```

## Automation (JSON + jq)

```bash
forge system memory --json | jq .percent
forge net dns google.com --json | jq .ipv4
forge files duplicates ~/data --json | jq '.[].files'
forge config show --json | jq .thresholds
```

## Doctor & Dashboard

```bash
forge doctor --verbose
forge dashboard --refresh 2
# JSON snapshot:
forge dashboard --json | jq .cpu.usage_percent
```
