import sqlite3
import sys
from pathlib import Path

import os
from common import setup_logging, get_logger

import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav
from dotenv import load_dotenv

load_dotenv()

setup_logging()
logger = get_logger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "transcripts.db"
AUDIO_SEGMENTS_DIR = Path(os.getenv("AUDIO_SEGMENTS", "/mnt/audio/audio_segments"))


def _kmeans(data: np.ndarray, k: int = 2, iterations: int = 20):
    if len(data) == 0:
        return [], []
    k = min(k, len(data))
    centroids = data[np.random.choice(len(data), k, replace=False)]
    for _ in range(iterations):
        groups = {i: [] for i in range(k)}
        for vec in data:
            idx = np.argmin([np.linalg.norm(vec - c) for c in centroids])
            groups[idx].append(vec)
        new_centroids = []
        for i in range(k):
            if groups[i]:
                new_centroids.append(np.mean(groups[i], axis=0))
            else:
                new_centroids.append(centroids[i])
        new_centroids = np.array(new_centroids)
        if np.allclose(new_centroids, centroids):
            break
        centroids = new_centroids
    labels = [np.argmin([np.linalg.norm(vec - c) for c in centroids]) for vec in data]
    return labels, centroids


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    return 1 - float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def main(recording_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT id, embedding_path FROM segments WHERE recording_id = ?",
        (recording_id,),
    ).fetchall()
    conn.close()

    if not rows:
        return

    encoder = VoiceEncoder()
    seg_info = []  # (id, path, embedding)
    embeddings = []
    for seg_id, path in rows:
        try:
            segment_path = Path(path)
            if not segment_path.is_absolute():
                segment_path = AUDIO_SEGMENTS_DIR / segment_path.name
            wav = preprocess_wav(str(segment_path))
            emb = encoder.embed_utterance(wav)
            seg_info.append((seg_id, str(segment_path), emb))
            embeddings.append(emb)
        except Exception:
            logger.exception(f"⚠️ Failed to process {segment_path}")
    embeddings = np.array(embeddings)
    if len(embeddings) == 0:
        return

    labels, centroids = _kmeans(embeddings, k=2)

    conn = sqlite3.connect(DB_PATH)
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

    # Load existing speaker averages
    existing = {}
    next_index = 0
    speaker_rows = cursor.execute("SELECT id FROM speakers").fetchall()
    for (sid,) in speaker_rows:
        if sid.startswith("speaker_"):
            try:
                idx = int(sid.split("_")[1])
                next_index = max(next_index, idx + 1)
            except ValueError:
                pass
        sample_ids = cursor.execute(
            "SELECT segment_id FROM speaker_samples WHERE speaker_id = ?",
            (sid,),
        ).fetchall()
        embs = []
        for (seg_id,) in sample_ids:
            row = cursor.execute(
                "SELECT embedding_path FROM segments WHERE id=?", (seg_id,)
            ).fetchone()
            if not row:
                continue
            try:
                wav = preprocess_wav(row[0])
                embs.append(encoder.embed_utterance(wav))
            except Exception:
                continue
        if embs:
            existing[sid] = np.mean(embs, axis=0)

    for label_idx in range(len(centroids)):
        cluster = [
            (seg_info[i][0], seg_info[i][1], embeddings[i])
            for i in range(len(embeddings))
            if labels[i] == label_idx
        ]
        if not cluster:
            continue
        centroid = centroids[label_idx]
        cluster.sort(key=lambda x: np.linalg.norm(x[2] - centroid))
        top = cluster[:10]
        rep = np.mean([vec for _, _, vec in top], axis=0)

        best_name = None
        best_dist = float("inf")
        for sid, avg in existing.items():
            dist = _cosine_distance(avg, rep)
            if dist < best_dist:
                best_dist = dist
                best_name = sid

        if best_name is None or best_dist > 0.2:
            speaker_name = f"speaker_{next_index}"
            next_index += 1
            cursor.execute(
                "INSERT OR IGNORE INTO speakers (id, label) VALUES (?, ?)",
                (speaker_name, ""),
            )
        else:
            speaker_name = best_name

        cursor.executemany(
            "UPDATE segments SET speaker_id=? WHERE id=?",
            [(speaker_name, seg_id) for seg_id, _, _ in cluster],
        )

        # Manage speaker sample references
        existing_samples = []
        rows = cursor.execute(
            "SELECT segment_id FROM speaker_samples WHERE speaker_id = ?",
            (speaker_name,),
        ).fetchall()
        for (seg_id,) in rows:
            row = cursor.execute(
                "SELECT embedding_path FROM segments WHERE id=?", (seg_id,)
            ).fetchone()
            if not row:
                continue
            try:
                wav = preprocess_wav(row[0])
                existing_samples.append((seg_id, encoder.embed_utterance(wav)))
            except Exception:
                continue

        all_samples = existing_samples + [(seg_id, emb) for seg_id, _, emb in top]
        all_samples.sort(key=lambda x: np.linalg.norm(x[1] - rep))
        selected = all_samples[:10]

        cursor.execute(
            "DELETE FROM speaker_samples WHERE speaker_id = ?", (speaker_name,)
        )
        cursor.executemany(
            "INSERT INTO speaker_samples (speaker_id, segment_id) VALUES (?, ?)",
            [(speaker_name, seg_id) for seg_id, _ in selected],
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Usage: speaker_identification.py RECORDING_ID")
        sys.exit(1)
    main(int(sys.argv[1]))
