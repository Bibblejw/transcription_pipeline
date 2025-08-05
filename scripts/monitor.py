import os
import time
import subprocess
from dotenv import load_dotenv

load_dotenv()

AUDIO_DIR = os.getenv("AUDIO")
TRANSCRIPTS_DIR = os.getenv("TRANSCRIPTS")
TRANSCRIBE_SCRIPT = "transcribe.py"
IDENTIFY_SCRIPT = "identify_speakers.py"
SUMMARISE_SCRIPT = "summarise.py"

POLL_INTERVAL = 60  # seconds

def get_all_audio_files():
    files = []
    for root, _, filenames in os.walk(AUDIO_DIR):
        for filename in filenames:
            if filename.lower().endswith(".m4a"):
                full_path = os.path.join(root, filename)
                files.append(full_path)
    return files

def filename_to_transcript_name(audio_path):
    # Convert e.g. "2025-08-03\\14-10-00.m4a" to "2025-08-03_14-10-00.txt"
    rel_path = os.path.relpath(audio_path, AUDIO_DIR)
    date_part, time_file = os.path.split(rel_path)
    time_part = os.path.splitext(time_file)[0]
    flat_name = f"{date_part}_{time_part}".replace("\\", "_").replace("/", "_") + ".txt"
    return flat_name

def run_pipeline():
    try:
        print("🔁 Running transcription...")
        subprocess.run(["python", TRANSCRIBE_SCRIPT], check=True)

        print("🧠 Running speaker identification...")
        subprocess.run(["python", IDENTIFY_SCRIPT], check=True)

        print("📝 Running summarisation...")
        subprocess.run(["python", SUMMARISE_SCRIPT], check=True)

        print("✅ All stages completed.\n")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during processing: {e}")

def monitor_loop():
    print(f"📡 Polling '{AUDIO_DIR}' every {POLL_INTERVAL} seconds...")
    while True:
        unprocessed_found = False
        audio_files = get_all_audio_files()
        for audio_path in audio_files:
            transcript_name = filename_to_transcript_name(audio_path)
            transcript_path = os.path.join(TRANSCRIPTS_DIR, transcript_name)
            if not os.path.exists(transcript_path):
                print(f"🎙️ New file detected: {audio_path}")
                run_pipeline()
                unprocessed_found = True
                break  # Stop after one new file to avoid overlap

        if not unprocessed_found:
            print("📭 No new files detected.")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    monitor_loop()
