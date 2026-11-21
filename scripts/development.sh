#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing ForgeKit in editable mode..."
pip install -e ".[dev]"

echo "==> Running ruff..."
ruff check src/ tests/ || true
ruff format src/ tests/ || true

echo "==> Running pytest..."
pytest -v

echo "==> Checking forge install..."
forge --help | head -n 20
forge doctor

echo "==> Done."
