#!/bin/bash
set -e

# Ensure working directory is the script's directory (repository root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate Python virtual environment if it exists (so python3 refers to the venv interpreter)
if [ -f ".venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source .venv/bin/activate
fi

# Enforce Python 3.11 for local runs to avoid compatibility issues
PY_VER=$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [ "$PY_VER" != "3.11" ]; then
    echo "❗️ Python $PY_VER detected. This project officially supports Python 3.11. Please use Python 3.11." >&2
    echo "Launching a shell so you can switch to Python 3.11 and then rerun './entrypoint.sh'." >&2
    exec "${SHELL:-/bin/bash}" || exit 1
fi

DB_PATH="${TRANSCRIPTS_DB:-/mnt/db/transcripts.db}"
if [ ! -f "$DB_PATH" ]; then
    python scripts/init_db.py
fi

exec python scripts/start_services.py
