"""CPU command — re-export for backwards compat."""

from forgekit.commands.system import cpu_cmd as cpu  # noqa: F401

# This module exists to satisfy repo structure; actual implementation is in system.py
