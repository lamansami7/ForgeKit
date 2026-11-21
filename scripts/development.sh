#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing ForgeKit in editable mode..."
pip install -e ".[dev]"

echo "==> Running ruff..."
ruff check src/ tests/
ruff format --check src/ tests/

echo "==> Running pytest with coverage gate..."
pytest -v --cov=forgekit --cov-report=term-missing

echo "==> Checking forge install..."
forge --help
forge --version
forge doctor

echo "==> Done."
