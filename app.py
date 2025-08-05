from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import sqlite3
from pathlib import Path
import sys
import subprocess
import os
from dotenv import load_dotenv
import numpy as np

sys.path.append(str(Path(__file__).parent / "scripts"))

load_dotenv()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

DB_PATH = Path(__file__).parent / "transcripts.db"
AUDIO_SEGMENTS_DIR = Path(os.getenv("AUDIO_SEGMENTS", "/mnt/audio/audio_segments"))
DASHBOARD_DIR = Path(__file__).parent / "dashboard"

# Static mounts
app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")
app.mount("/segments", StaticFiles(directory=AUDIO_SEGMENTS_DIR), name="segments")


@app.get("/")
@app.get("/index")
@app.get("/index.html")
def index():
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.get("/jobs")
@app.get("/jobs.html")
def jobs_page():
    """Serve the jobs dashboard page."""
    return FileResponse(DASHBOARD_DIR / "jobs.html")


@app.get("/speakers")
@app.get("/speakers.html")
def speakers_page():
    """Serve the speakers dashboard page."""
    return FileResponse(DASHBOARD_DIR / "speakers.html")


@app.get("/transcripts")
@app.get("/transcripts.html")
def transcripts_page():
    """Serve the transcripts dashboard page."""
    return FileResponse(DASHBOARD_DIR / "transcripts.html")


@app.get("/transcript")
@app.get("/transcript.html")
def transcript_page():
    """Serve the transcript detail page."""
    return FileResponse(DASHBOARD_DIR / "transcript.html")


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
    """Process a single job by ID."""
    try:
        result = _process_job(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "completed", "recording_id": result.get("recording_id")}


class JobBatch(BaseModel):
    job_ids: list[int]


def _process_job(job_id: int):
    from transcribe_and_split import transcribe_and_split

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    row = cursor.execute("SELECT file_path FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError("Job not found")
    file_path = row[0]
    try:
        cursor.execute("UPDATE jobs SET status = 'processing' WHERE id = ?", (job_id,))
        conn.commit()
        recording_id = transcribe_and_split(Path(file_path))
        if recording_id is not None:
            run_speaker_identification(recording_id)
        cursor.execute("UPDATE jobs SET status = 'completed' WHERE id = ?", (job_id,))
        conn.commit()
        return {"job_id": job_id, "recording_id": recording_id}
    except Exception as e:
        cursor.execute("UPDATE jobs SET status = 'error' WHERE id = ?", (job_id,))
        conn.commit()
        raise e
    finally:
        conn.close()


@app.post("/api/jobs/batch")
def process_jobs_batch(batch: JobBatch):
    """Process multiple jobs in sequence."""
    processed = []
    errors = []
    for job_id in batch.job_ids:
        try:
            processed.append(_process_job(job_id))
        except ValueError:
            errors.append({"job_id": job_id, "error": "not found"})
        except Exception as e:
            errors.append({"job_id": job_id, "error": str(e)})
    return {"processed": processed, "errors": errors}
            
@app.get("/api/segments/{recording_id}")
def get_segments(recording_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
    SELECT s.id, s.start_time, s.end_time, s.speaker_id, sp.label AS speaker_label,
           s.transcript, s.embedding_path
    FROM segments s
    LEFT JOIN speakers sp ON sp.id = s.speaker_id
    WHERE s.recording_id = ?
    ORDER BY s.start_time ASC
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


def run_speaker_identification(recording_id: int):
    """Invoke the speaker identification script for a given recording."""
    script = Path(__file__).parent / "scripts" / "speaker_identification.py"
    try:
        subprocess.run([sys.executable, str(script), str(recording_id)], check=True)
    except subprocess.CalledProcessError as exc:
        print(f"⚠️ Speaker identification failed: {exc}")


@app.post("/api/recordings/{recording_id}/identify")
def identify_recording(recording_id: int, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_speaker_identification, recording_id)
    return {"status": "started"}


class RecordingBatch(BaseModel):
    recording_ids: list[int]


@app.post("/api/recordings/identify_batch")
def identify_recordings_batch(batch: RecordingBatch, background_tasks: BackgroundTasks):
    for rid in batch.recording_ids:
        background_tasks.add_task(run_speaker_identification, rid)
    return {"status": "started", "count": len(batch.recording_ids)}


class SpeakerUpdate(BaseModel):
    label: str


class SegmentSpeakerUpdate(BaseModel):
    speaker_id: str


class SpeakerMerge(BaseModel):
    source_id: str
    target_id: str


@app.get("/api/speakers")
def get_speakers():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS speaker_samples (
            speaker_id TEXT,
            segment_id INTEGER,
            FOREIGN KEY (speaker_id) REFERENCES speakers(id),
            FOREIGN KEY (segment_id) REFERENCES segments(id)
        )
        """
    )
    rows = cursor.execute("SELECT id, label FROM speakers ORDER BY id").fetchall()
    speakers = []
    for row in rows:
        samples = cursor.execute(
            """
            SELECT s.id, s.embedding_path
            FROM speaker_samples sp
            JOIN segments s ON s.id = sp.segment_id
            WHERE sp.speaker_id = ?
            ORDER BY sp.rowid DESC
            """,
            (row["id"],),
        ).fetchall()
        speakers.append(
            {
                "id": row["id"],
                "label": row["label"],
                "samples": [
                    {"id": s[0], "file": Path(s[1]).name if s[1] else None}
                    for s in samples
                ],
            }
        )
    conn.close()
    return speakers


@app.post("/api/speakers/{speaker_id}")
def update_speaker(speaker_id: str, payload: SpeakerUpdate):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE speakers SET label = ? WHERE id = ?", (payload.label, speaker_id)
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/speakers/merge")
def merge_speakers(payload: SpeakerMerge):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE segments SET speaker_id = ? WHERE speaker_id = ?",
        (payload.target_id, payload.source_id),
    )
    cursor.execute(
        "UPDATE speaker_samples SET speaker_id = ? WHERE speaker_id = ?",
        (payload.target_id, payload.source_id),
    )
    cursor.execute(
        """
        DELETE FROM speaker_samples
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM speaker_samples
            GROUP BY speaker_id, segment_id
        )
        """
    )
    cursor.execute(
        "SELECT label FROM speakers WHERE id = ?",
        (payload.target_id,),
    )
    target_row = cursor.fetchone()
    if target_row and not target_row[0]:
        cursor.execute(
            "SELECT label FROM speakers WHERE id = ?",
            (payload.source_id,),
        )
        source_row = cursor.fetchone()
        if source_row and source_row[0]:
            cursor.execute(
                "UPDATE speakers SET label = ? WHERE id = ?",
                (source_row[0], payload.target_id),
            )
    cursor.execute("DELETE FROM speakers WHERE id = ?", (payload.source_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/segments/{segment_id}/speaker")
def update_segment_speaker(segment_id: int, payload: SegmentSpeakerUpdate):
    """Assign a segment to a speaker and suggest similar segments."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE segments SET speaker_id = ? WHERE id = ?",
        (payload.speaker_id, segment_id),
    )
    conn.commit()

    row = cursor.execute(
        "SELECT embedding_path, recording_id FROM segments WHERE id = ?",
        (segment_id,),
    ).fetchone()

    candidates: list[int] = []
    if row and row[0]:
        emb_path = Path(row[0])
        if not emb_path.is_absolute():
            emb_path = AUDIO_SEGMENTS_DIR / emb_path.name
        try:
            from resemblyzer import VoiceEncoder, preprocess_wav

            encoder = VoiceEncoder()
            wav = preprocess_wav(str(emb_path))
            target_emb = encoder.embed_utterance(wav)

            others = cursor.execute(
                "SELECT id, embedding_path FROM segments WHERE recording_id = ? AND id != ?",
                (row[1], segment_id),
            ).fetchall()

            for sid, path in others:
                if not path:
                    continue
                path = Path(path)
                if not path.is_absolute():
                    path = AUDIO_SEGMENTS_DIR / path.name
                try:
                    wav2 = preprocess_wav(str(path))
                    emb2 = encoder.embed_utterance(wav2)
                    dist = 1 - float(np.dot(target_emb, emb2) / (np.linalg.norm(target_emb) * np.linalg.norm(emb2) + 1e-10))
                    if dist < 0.25:
                        candidates.append(sid)
                except Exception:
                    continue
        except Exception:
            pass

    conn.close()
    return {"status": "ok", "candidates": candidates}
