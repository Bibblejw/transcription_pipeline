from fastapi import FastAPI, HTTPException, BackgroundTasks
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
GLOBAL_SPEAKERS_PATH = Path(__file__).parent / "global_speakers.json"

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


def _compute_segment_feature(path: str) -> float:
    """Return a simple average absolute amplitude feature for the audio segment."""
    import wave
    import struct
    try:
        with wave.open(path, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            samples = struct.unpack("<" + "h" * (len(frames) // 2), frames)
            return sum(abs(s) for s in samples) / max(1, len(samples))
    except Exception as e:
        print(f"⚠️ Failed to read {path}: {e}")
        return 0.0


def _kmeans_1d(values, k: int = 2, iterations: int = 20):
    """Very small 1D k-means implementation using only stdlib."""
    import random

    if not values:
        return [], []
    k = min(k, len(set(values))) or 1
    centroids = random.sample(values, k)
    for _ in range(iterations):
        groups = {i: [] for i in range(k)}
        for v in values:
            idx = min(range(k), key=lambda j: abs(v - centroids[j]))
            groups[idx].append(v)
        new_centroids = [
            sum(g) / len(g) if g else centroids[i] for i, g in groups.items()
        ]
        if all(abs(new_centroids[i] - centroids[i]) < 1e-3 for i in range(k)):
            break
        centroids = new_centroids
    labels = [min(range(k), key=lambda j: abs(v - centroids[j])) for v in values]
    return labels, centroids


def run_speaker_identification(recording_id: int):
    import json
    import math

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT id, embedding_path FROM segments WHERE recording_id = ?",
        (recording_id,),
    ).fetchall()

    if not rows:
        conn.close()
        return

    segment_features = []
    segment_ids = []
    for seg_id, path in rows:
        feature = _compute_segment_feature(path)
        segment_features.append(feature)
        segment_ids.append((seg_id, path, feature))

    labels, centroids = _kmeans_1d(segment_features, k=2)

    # Load global speaker data
    if GLOBAL_SPEAKERS_PATH.exists():
        global_map = json.loads(GLOBAL_SPEAKERS_PATH.read_text())
    else:
        global_map = {}

    next_index = 0
    for name in global_map.keys():
        if name.startswith("speaker_"):
            try:
                idx = int(name.split("_")[1])
                next_index = max(next_index, idx + 1)
            except ValueError:
                continue

    # Group segments by label
    groups = {}
    for (seg_id, path, feat), label in zip(segment_ids, labels):
        groups.setdefault(label, []).append((seg_id, path, feat))

    for label, items in groups.items():
        centroid = centroids[label]
        # pick up to 10 closest segments
        items.sort(key=lambda x: abs(x[2] - centroid))
        selected = items[:10]

        best_name = None
        best_diff = math.inf
        for name, info in global_map.items():
            samples = info.get("samples", [])
            if not samples:
                continue
            avg = sum(samples) / len(samples)
            diff = abs(avg - centroid)
            if diff < best_diff:
                best_diff = diff
                best_name = name

        if best_name is None or best_diff > 500:
            speaker_name = f"speaker_{next_index}"
            next_index += 1
            global_map[speaker_name] = {"samples": [centroid]}
        else:
            speaker_name = best_name
            global_map[speaker_name]["samples"].append(centroid)

        cursor.executemany(
            "UPDATE segments SET speaker_id=? WHERE id=?",
            [(speaker_name, seg_id) for seg_id, _, _ in items],
        )

    conn.commit()
    conn.close()
    GLOBAL_SPEAKERS_PATH.write_text(json.dumps(global_map, indent=2))


@app.post("/api/recordings/{recording_id}/identify")
def identify_recording(recording_id: int, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_speaker_identification, recording_id)
    return {"status": "started"}
