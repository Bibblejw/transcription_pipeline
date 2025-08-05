from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import sqlite3
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent / "scripts"))

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

DB_PATH = Path(__file__).parent / "transcripts.db"
AUDIO_SEGMENTS_DIR = "/mnt/audio/audio_segments"
DASHBOARD_DIR = Path(__file__).parent / "dashboard"

# Static mounts
app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")
app.mount("/segments", StaticFiles(directory=AUDIO_SEGMENTS_DIR), name="segments")


@app.get("/")
def index():
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.get("/api/recordings")
def get_recordings():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
    SELECT r.id, r.filename, r.datetime, r.duration_sec,
           COUNT(s.id) AS segment_count
    FROM recordings r
    LEFT JOIN segments s ON s.recording_id = r.id
    GROUP BY r.id
    ORDER BY r.datetime DESC
    """
    rows = cursor.execute(query).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/jobs")
def get_jobs():
    """Return all jobs with their status and creation time."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT id, file_path, status, created_at FROM jobs ORDER BY created_at DESC"
    ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/jobs/{job_id}/process")
def process_job(job_id: int):
    from transcribe_and_split import transcribe_and_split

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    row = cursor.execute("SELECT file_path FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    file_path = row[0]
    try:
        cursor.execute("UPDATE jobs SET status = 'processing' WHERE id = ?", (job_id,))
        conn.commit()
        transcribe_and_split(Path(file_path))
        cursor.execute("UPDATE jobs SET status = 'completed' WHERE id = ?", (job_id,))
        conn.commit()
    except Exception as e:
        cursor.execute("UPDATE jobs SET status = 'error' WHERE id = ?", (job_id,))
        conn.commit()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"status": "completed"}
            
@app.get("/api/segments/{recording_id}")
def get_segments(recording_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
    SELECT id, start_time, end_time, speaker_id, transcript, embedding_path
    FROM segments
    WHERE recording_id = ?
    ORDER BY start_time ASC
    """
    rows = cursor.execute(query, (recording_id,)).fetchall()
    return [dict(row) for row in rows]


@app.delete("/api/recordings/{recording_id}")
def delete_recording(recording_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT filename FROM recordings WHERE id = ?", (recording_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Find and delete associated audio segment files
    cursor.execute("SELECT embedding_path FROM segments WHERE recording_id = ?", (recording_id,))
    for (path,) in cursor.fetchall():
        if path and Path(path).exists():
            try:
                Path(path).unlink()
            except Exception as e:
                print(f"⚠️ Failed to delete {path}: {e}")

    cursor.execute("DELETE FROM segments WHERE recording_id = ?", (recording_id,))
    cursor.execute("DELETE FROM recordings WHERE id = ?", (recording_id,))
    conn.commit()
    conn.close()

    return {"status": "deleted", "id": recording_id}
