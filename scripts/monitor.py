import os
import time
import subprocess
from pathlib import Path

import requests
from dotenv import load_dotenv

from common import setup_logging, get_logger
from transcribe_and_split import transcribe_and_split

load_dotenv()
setup_logging()
logger = get_logger(__name__)

AUDIO_DIR = os.getenv("AUDIO")

POLL_INTERVAL = 60  # seconds

def get_all_audio_files():
    files = []
    for root, _, filenames in os.walk(AUDIO_DIR):
        for filename in filenames:
            if filename.lower().endswith(".m4a"):
                full_path = os.path.join(root, filename)
                files.append(full_path)
    return files

def process_file(audio_path):
    """Transcribe, identify speakers, and summarise a single audio file."""
    try:
        logger.info(f"🔁 Transcribing and splitting: {audio_path}")
        recording_id = transcribe_and_split(Path(audio_path).resolve())
        if recording_id is None:
            logger.info("⏭️  File already processed or failed during transcription.")
            return False

        logger.info(f"🧠 Identifying speakers for recording {recording_id}...")
        subprocess.run(
            ["python", "speaker_identification.py", str(recording_id)], check=True
        )

        logger.info(f"📝 Requesting summarisation for recording {recording_id}...")
        resp = requests.post(
            f"http://127.0.0.1:8000/api/recordings/{recording_id}/summarize"
        )
        resp.raise_for_status()
        logger.info("✅ All stages completed.\n")
        return True
    except subprocess.CalledProcessError:
        logger.exception("❌ Error during speaker identification")
    except requests.RequestException:
        logger.exception("❌ Error during summarisation request")
    except Exception:
        logger.exception("❌ Unexpected error during processing")
    return False

def monitor_loop():
    logger.info(f"📡 Polling '{AUDIO_DIR}' every {POLL_INTERVAL} seconds...")
    while True:
        processed_any = False
        audio_files = get_all_audio_files()
        for audio_path in audio_files:
            if process_file(audio_path):
                processed_any = True
                break  # Stop after one new file to avoid overlap

        if not processed_any:
            logger.info("📭 No new files detected.")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    monitor_loop()
