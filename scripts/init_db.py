import sqlite3
from pathlib import Path

db_path = Path("~/transcription_pipeline/transcripts.db")
db_path.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.executescript("""
CREATE TABLE IF NOT EXISTS recordings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    datetime TEXT,
    duration_sec REAL
);

CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id INTEGER NOT NULL,
    start_time REAL,
    end_time REAL,
    speaker_id TEXT,
    transcript TEXT,
    embedding_path TEXT,
    FOREIGN KEY (recording_id) REFERENCES recordings(id)
);

CREATE TABLE IF NOT EXISTS speakers (
    id TEXT PRIMARY KEY,
    label TEXT,
    profile_path TEXT,
    last_seen TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
""")

conn.commit()
conn.close()

print(f"✅ Database initialized at: {db_path.resolve()}")
