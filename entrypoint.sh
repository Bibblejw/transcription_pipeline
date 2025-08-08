#!/bin/bash
set -e

DB_PATH="${TRANSCRIPTS_DB:-/mnt/db/transcripts.db}"
if [ ! -f "$DB_PATH" ]; then
    python scripts/init_db.py
fi

exec python scripts/start_services.py
