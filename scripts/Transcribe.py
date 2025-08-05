import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()
API_KEY = os.getenv("WHISPERAPI")
AUDIO_DIR = os.getenv("AUDIO")
TRANSCRIPTS_DIR = os.getenv("TRANSCRIPTS")
API_URL = "https://api.lemonfox.ai/v1/audio/transcriptions"

def get_unprocessed_files():
    """
    Recursively find all .m4a files in AUDIO_DIR whose corresponding
    output file doesn't already exist in TRANSCRIPTS_DIR.
    """
    processed = {
        os.path.splitext(f)[0] for f in os.listdir(TRANSCRIPTS_DIR) if f.endswith(".txt")
    }
    unprocessed_files = []

    for root, _, files in os.walk(AUDIO_DIR):
        for file in files:
            if file.endswith(".m4a"):
                date_part = os.path.basename(root)
                time_part = os.path.splitext(file)[0]
                output_name = f"{date_part}_{time_part}"
                if output_name not in processed:
                    full_path = os.path.join(root, file)
                    unprocessed_files.append(full_path)

    return unprocessed_files

def transcribe(file_path):
    """
    Send the file to the Lemonfox Whisper API and return the JSON result.
    """
    headers = {"Authorization": f"Bearer {API_KEY}"}
    data = {
        "language": "english",
        "speaker_labels": "true",
        "response_format": "verbose_json"
    }

    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(API_URL, headers=headers, data=data, files=files)

    response.raise_for_status()
    return response.json()

def save_transcript(file_path, segments):
    """
    Save the transcript to OUTPUT directory using the format DATE_TIME.txt
    based on the input folder/file name.
    """
    parts = os.path.normpath(file_path).split(os.sep)
    date_part = parts[-2]   # e.g., 2025-07-27
    time_part = os.path.splitext(parts[-1])[0]  # e.g., 14-10-34

    filename = f"{date_part}_{time_part}.txt"
    output_path = os.path.join(TRANSCRIPTS_DIR, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        for segment in segments:
            speaker = segment.get("speaker", "Speaker")
            text = segment["text"]
            f.write(f"[{speaker}] {text}\n")

def main():
    if not API_KEY or not AUDIO_DIR or not TRANSCRIPTS_DIR:
        print("❌ Missing WHISPERAPI, AUDIO, or OUTPUT in .env")
        return

    os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

    print(f"📁 Input:    {AUDIO_DIR}")
    print(f"📁 Output:   {TRANSCRIPTS_DIR}")
    print("🔍 Searching for new audio files...")

    for file_path in get_unprocessed_files():
        print(f"🎙️ Transcribing: {file_path}")
        try:
            result = transcribe(file_path)
            segments = result.get("segments", [])
            save_transcript(file_path, segments)
            print(f"✅ Transcript saved for: {file_path}")
        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}")

if __name__ == "__main__":
    main()
