#!/bin/bash
set -e

# Activate Python virtual environment if it exists (so python3 refers to the venv interpreter)
if [ -f ".venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source .venv/bin/activate
fi

# Enforce Python 3.11 for local runs to avoid compatibility issues
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [ "$PY_VER" != "3.11" ]; then
    echo "❗️ Python $PY_VER detected. This project officially supports Python 3.11. Please use Python 3.11." >&2
    exit 1
fi

DB_PATH="${TRANSCRIPTS_DB:-/mnt/db/transcripts.db}"
if [ ! -f "$DB_PATH" ]; then
    python3 scripts/init_db.py
fi

exec python3 scripts/start_services.py
