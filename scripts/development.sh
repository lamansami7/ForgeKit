#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing ForgeKit in editable mode..."
pip install -e ".[dev]"

echo "==> Running ruff..."
ruff check src/ tests/
ruff format --check src/ tests/

echo "==> Running pytest..."
pytest -v

echo "==> Checking forge install..."
forge --help
forge doctor

echo "==> Done."
