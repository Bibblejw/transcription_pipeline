import os
import sqlite3
from pathlib import Path
from pydub import AudioSegment
from dotenv import load_dotenv
import whisper
from common import setup_logging, get_logger
import vad_split

# === Load environment ===
load_dotenv()
setup_logging()
logger = get_logger(__name__)

AUDIO_DIR = Path(os.getenv("AUDIO"))
SEGMENT_DIR = Path(os.getenv("AUDIO_SEGMENTS", "/mnt/audio/audio_segments")).resolve()
TRANSCRIPTS_DB = Path(os.getenv("TRANSCRIPTS_DB"))

SEGMENT_DIR.mkdir(parents=True, exist_ok=True)

# === Load Whisper model ===
model = whisper.load_model("base")  # or "medium", "small", etc.

def transcribe_and_split(audio_path: Path):
    """Transcribe ``audio_path`` and split it into segments.

    Returns the ``recording_id`` of the newly inserted row in the
    ``recordings`` table.  ``None`` is returned if the file was skipped or an
    error occurred.
    """
    conn = sqlite3.connect(TRANSCRIPTS_DB)
    cursor = conn.cursor()
    recording_id = None
    try:
        # Extract standard datetime ID from filename
        parts = audio_path.relative_to(AUDIO_DIR).parts
        date_part = parts[-2] if len(parts) >= 2 else "unknown"
        time_part = Path(parts[-1]).stem
        transcript_id = f"{date_part}_{time_part}"

        # 🔁 Skip if already in DB
        cursor.execute("SELECT 1 FROM recordings WHERE datetime = ?", (transcript_id,))
        if cursor.fetchone():
            print(f"⏩ Already processed: {transcript_id}")
            return None

        print(f"🎙️ Transcribing: {audio_path}")
        audio = AudioSegment.from_file(audio_path)
        vad_segments = vad_split.split_audio(audio_path, SEGMENT_DIR, prefix=transcript_id)

        # Insert into recordings table
        cursor.execute(
            "INSERT INTO recordings (filename, datetime, duration_sec) VALUES (?, ?, ?)",
            (audio_path.name, transcript_id, len(audio) / 1000),
        )
        recording_id = cursor.lastrowid

        for start_sec, end_sec, segment_path in vad_segments:
            transcription = model.transcribe(str(segment_path), verbose=False, language="en")
            cursor.execute("""
                INSERT INTO segments (
                    recording_id, start_time, end_time, speaker_id, transcript, embedding_path
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                recording_id,
                start_sec,
                end_sec,
                None,
                transcription['text'].strip(),
                str(segment_path)
            ))

        conn.commit()
        logger.info(f"✅ Completed: {transcript_id}")
        return recording_id

    except Exception:
        logger.exception(f"❌ Failed to process {audio_path.name}")
        return None
    finally:
        conn.close()

def main():
    audio_files = list(AUDIO_DIR.rglob("*.m4a"))
    logger.info(f"🔍 Found {len(audio_files)} file(s) in {AUDIO_DIR}")

    for audio_file in audio_files:
        transcribe_and_split(audio_file)

if __name__ == "__main__":
    main()
