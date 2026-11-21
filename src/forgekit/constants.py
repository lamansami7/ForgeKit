"""Constants for ForgeKit."""

from pathlib import Path

APP_NAME = "forgekit"
APP_DISPLAY_NAME = "ForgeKit"
APP_VERSION = "0.1.0"

# Config paths
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "forgekit"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.toml"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "forgekit"
DEFAULT_HISTORY_FILE = DEFAULT_CACHE_DIR / "history.db"

# Thresholds
CPU_WARNING_THRESHOLD = 80.0
MEMORY_WARNING_THRESHOLD = 85.0
DISK_WARNING_THRESHOLD = 85.0
DISK_CRITICAL_THRESHOLD = 95.0

# Dashboard
DEFAULT_DASHBOARD_REFRESH = 2.0  # seconds
MIN_DASHBOARD_REFRESH = 0.5

# Network
DEFAULT_PING_COUNT = 4
DEFAULT_PING_TIMEOUT = 5
DEFAULT_DNS_TIMEOUT = 5
DEFAULT_HTTP_TIMEOUT = 10
DEFAULT_CONNECTIVITY_HOSTS = [
    "https://1.1.1.1",
    "https://8.8.8.8",
    "https://google.com",
]

# Files
DEFAULT_LARGE_FILE_THRESHOLD_MB = 100
DEFAULT_EXCLUDE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".cache"}

# Backup
BACKUP_MANIFEST_NAME = ".forgekit-backup.json"

# Colors
COLORS = {
    "primary": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "info": "blue",
    "muted": "dim",
}

BANNER = r"""
[bold cyan]  ███████╗ ██████╗ ██████╗  ██████╗ ███████╗[/bold cyan][bold white] ██╗  ██╗██╗████████╗[/bold white]
[bold cyan]  ██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝[/bold cyan][bold white] ██║ ██╔╝██║╚══██╔══╝[/bold white]
[bold cyan]  █████╗  ██║   ██║██████╔╝██║  ███╗█████╗  [/bold cyan][bold white] █████╔╝ ██║   ██║   [/bold white]
[bold cyan]  ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝  [/bold cyan][bold white] ██╔═██╗ ██║   ██║   [/bold white]
[bold cyan]  ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗[/bold cyan][bold white] ██║  ██╗██║   ██║   [/bold white]
[bold cyan]  ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝[/bold cyan][bold white] ╚═╝  ╚═╝╚═╝   ╚═╝   [/bold white]
"""

BANNER_SUBTITLE = "[dim]A powerful modular toolkit for Linux, developers & system diagnostics[/dim]"
