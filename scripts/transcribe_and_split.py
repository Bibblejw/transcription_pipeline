import os
import sqlite3
from pathlib import Path
from pydub import AudioSegment
from dotenv import load_dotenv
import whisper

# === Load environment ===
load_dotenv()

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
        result = model.transcribe(str(audio_path), verbose=False, language="en")

        # Insert into recordings table
        cursor.execute(
            "INSERT INTO recordings (filename, datetime, duration_sec) VALUES (?, ?, ?)",
            (audio_path.name, transcript_id, len(audio) / 1000),
        )
        recording_id = cursor.lastrowid

        for i, segment in enumerate(result['segments']):
            start_ms = int(segment['start'] * 1000)
            end_ms = int(segment['end'] * 1000)
            segment_audio = audio[start_ms:end_ms]

            segment_filename = f"{transcript_id}_seg{i:03d}.wav"
            segment_path = SEGMENT_DIR / segment_filename
            segment_audio.export(segment_path, format="wav")

            cursor.execute("""
                INSERT INTO segments (
                    recording_id, start_time, end_time, speaker_id, transcript, embedding_path
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                recording_id,
                segment['start'],
                segment['end'],
                None,
                segment['text'].strip(),
                str(segment_path)
            ))

        conn.commit()
        print(f"✅ Completed: {transcript_id}")
        return recording_id

    except Exception as e:
        print(f"❌ Failed to process {audio_path.name}: {e}")
        return None
    finally:
        conn.close()

def main():
    audio_files = list(AUDIO_DIR.rglob("*.m4a"))
    print(f"🔍 Found {len(audio_files)} file(s) in {AUDIO_DIR}")

    for audio_file in audio_files:
        transcribe_and_split(audio_file)

if __name__ == "__main__":
    main()
