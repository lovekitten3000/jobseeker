#!/bin/bash
set -euo pipefail

# Install dependencies for Claude Code on the web sessions only.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Runtime deps (PRD §7.2 / docs/ENVIRONMENT.md) plus dev tools for tests and linting.
pip install --break-system-packages typst pyyaml httpx pydantic pytest ruff

# Fail loudly at startup rather than silently mid-sweep.
python3 -c "import typst, yaml, httpx, pydantic"
python3 -m pytest --version
ruff --version
