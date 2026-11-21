"""Logging setup for ForgeKit."""

import logging
import sys

from forgekit.constants import APP_NAME


def get_logger(name: str = APP_NAME) -> logging.Logger:
    return logging.getLogger(name)


def setup_logging(level: str = "WARNING") -> None:
    numeric = getattr(logging, level.upper(), logging.WARNING)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root = logging.getLogger(APP_NAME)
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric)
