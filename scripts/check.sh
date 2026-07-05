#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> ruff check"
uv run ruff check .

echo "==> ruff format --check"
uv run ruff format --check .

echo "==> mypy"
uv run mypy app

echo "==> pytest"
uv run pytest -q

echo "==> validate data"
uv run python scripts/validate.py
