import sys
import os
import sqlite3
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

from common import setup_logging, get_logger
from maintain_global_speakers import load_global_map, save_global_map, update_global_map

# === Setup ===
load_dotenv()
setup_logging()
logger = get_logger(__name__)

DB_PATH = Path(os.getenv("TRANSCRIPTS_DB", Path(__file__).resolve().parent.parent / "transcripts.db"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "Given a collection of utterances from a single speaker, "
    "infer the most likely name or role (e.g., Jozef, Alex, Manager). "
    "Return a short label."
)

def fetch_segments(recording_id: int) -> dict[str, list[str]]:
    """Retrieve segments grouped by speaker_id for a recording."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT speaker_id, transcript
        FROM segments
        WHERE recording_id = ?
        ORDER BY start_time ASC
        """,
        (recording_id,),
    ).fetchall()
    conn.close()

    grouped: dict[str, list[str]] = {}
    for speaker_id, transcript in rows:
        if not speaker_id or not transcript:
            continue
        grouped.setdefault(speaker_id, []).append(transcript)
    return grouped

def infer_label(text: str) -> str | None:
    """Call OpenAI to infer a human-friendly label."""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        logger.exception("⚠️ GPT error")
        return None

def update_speaker_labels(recording_id: int, labels: dict[str, str]):
    """Persist speaker labels to DB and global_speakers.json."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for speaker_id, label in labels.items():
        cursor.execute(
            "INSERT INTO speakers (id, label) VALUES (?, ?) "
            "ON CONFLICT(id) DO UPDATE SET label=excluded.label",
            (speaker_id, label),
        )
    conn.commit()
    conn.close()

    global_map = load_global_map()
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    pseudo_file = f"{timestamp}_rec{recording_id}.txt"
    for speaker_id, label in labels.items():
        global_map = update_global_map(global_map, {speaker_id: label}, pseudo_file)
    save_global_map(global_map)

def main(recording_id: int):
    segments = fetch_segments(recording_id)
    if not segments:
        logger.error(f"No segments found for recording {recording_id}")
        return

    labels: dict[str, str] = {}
    for speaker_id, parts in segments.items():
        text = "\n".join(parts)
        logger.info(f"Labelling {speaker_id} with {len(parts)} utterances")
        label = infer_label(text)
        if label:
            labels[speaker_id] = label
            logger.info(f"→ {speaker_id} identified as {label}")
        else:
            logger.warning(f"Failed to label {speaker_id}")

    if not labels:
        return

    update_speaker_labels(recording_id, labels)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Usage: label_speakers.py RECORDING_ID")
        sys.exit(1)
    try:
        rec_id = int(sys.argv[1])
    except ValueError:
        logger.error("Recording ID must be an integer")
        sys.exit(1)
    main(rec_id)
