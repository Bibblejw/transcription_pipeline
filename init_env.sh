#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# Bootstrap the local development environment:
#  - ensures Python 3.11 is available
#  - creates and activates .venv
#  - installs dependencies
#  - copies .env.example to .env (if missing)
# -----------------------------------------------------------------------------

# Require Python 3.11
if ! command -v python3.11 >/dev/null 2>&1; then
  echo "❗️ python3.11 is required but not found. Install Python 3.11 and retry." >&2
  exit 1
fi

# Create virtualenv if needed
if [ ! -d .venv ]; then
  python3.11 -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate

# Upgrade pip and install requirements
pip install --upgrade pip
pip install -r requirements.txt

# Copy example env file
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — please edit it for your environment."
fi

echo "✅ Environment bootstrapped. Activate with 'source .venv/bin/activate' and run './entrypoint.sh'"
