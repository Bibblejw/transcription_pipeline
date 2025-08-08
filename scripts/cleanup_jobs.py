import os
import sqlite3
from pathlib import Path
from common import setup_logging, get_logger

try:  # python-dotenv may not be installed
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = lambda: None

load_dotenv()
setup_logging()
logger = get_logger(__name__)

DB_PATH = os.getenv("TRANSCRIPTS_DB")


def cleanup_jobs_queue():
    """Remove jobs whose recordings already exist in the database."""
    if not DB_PATH:
        raise RuntimeError("TRANSCRIPTS_DB must be set in the environment")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, file_path FROM jobs")
    jobs = cursor.fetchall()
    removed = 0

    for job_id, file_path in jobs:
        filename = Path(file_path).name
        cursor.execute("SELECT 1 FROM recordings WHERE filename = ?", (filename,))
        if cursor.fetchone():
            cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            logger.info(f"🗑️ Removed completed job for: {filename}")
            removed += 1

    conn.commit()
    conn.close()
    logger.info(f"✅ Removed {removed} completed job(s)")


if __name__ == "__main__":
    cleanup_jobs_queue()
