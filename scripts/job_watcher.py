import os
import time
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

AUDIO_DIR = os.getenv("AUDIO")
DB_PATH = os.getenv("TRANSCRIPTS_DB")
POLL_INTERVAL = 60  # seconds

def scan_for_new_files():
    """Recursively scan the audio directory and queue new files."""
    if not AUDIO_DIR or not DB_PATH:
        raise RuntimeError("AUDIO and TRANSCRIPTS_DB must be set in the environment")

    root_dir = Path(AUDIO_DIR)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    def iter_audio_files():
        for dirpath, _, filenames in os.walk(root_dir):
            for name in filenames:
                if name.lower().endswith(".m4a"):
                    yield Path(dirpath) / name

    print(f"📡 Monitoring '{root_dir}' for new audio files...")
    try:
        while True:
            for path in iter_audio_files():
                # Skip files already transcribed
                cursor.execute("SELECT 1 FROM recordings WHERE filename = ?", (path.name,))
                if cursor.fetchone():
                    continue

                # Skip files already queued as jobs
                cursor.execute("SELECT 1 FROM jobs WHERE file_path = ?", (str(path),))
                if cursor.fetchone():
                    continue

                cursor.execute(
                    "INSERT INTO jobs (file_path, status) VALUES (?, 'pending')",
                    (str(path),),
                )
                conn.commit()
                print(f"📥 Queued job for: {path}")

            time.sleep(POLL_INTERVAL)
    finally:
        conn.close()

if __name__ == "__main__":
    scan_for_new_files()
