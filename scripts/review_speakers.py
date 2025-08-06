import os
import json
import logging
import builtins
from dotenv import load_dotenv
from logging_config import setup_logging
from maintain_global_speakers import (
    load_global_map,
    save_global_map,
    update_global_map
)

# === Load environment variables ===
load_dotenv()
setup_logging()
builtins.print = lambda *args, **kwargs: logging.getLogger(__name__).info(" ".join(str(a) for a in args), **kwargs)
SPEAKER_MAPS_DIR = os.getenv("SPEAKER_MAPS")
TRANSCRIPTS_DIR = os.getenv("TRANSCRIPTS")
LABELLED_TRANSCRIPTS_DIR = os.getenv("TRANSCRIPTS_LABELLED")

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def save_text(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def relabel_transcript(text, speaker_map):
    for original, replacement in speaker_map.items():
        text = text.replace(f"{original}:", f"{replacement}:")
        text = text.replace(f"[{original}]", f"[{replacement}]")
    return text

def list_transcripts():
    return sorted(
        [f for f in os.listdir(SPEAKER_MAPS_DIR) if f.endswith(".json")]
    )

def edit_mapping(mapping):
    updated = {}
    print("\n📋 Current speaker map:")
    for key, val in mapping.items():
        new_val = input(f"🗣️ {key} → {val} | New name (leave blank to keep): ").strip()
        updated[key] = new_val if new_val else val
    return updated

def main():
    global_map = load_global_map()
    transcript_files = list_transcripts()

    if not transcript_files:
        print("No speaker maps found to review.")
        return

    print("📂 Available transcripts:\n")
    for i, fname in enumerate(transcript_files):
        print(f"[{i}] {fname}")

    choice = input("\n🔍 Enter number of transcript to review: ").strip()
    try:
        index = int(choice)
        selected_file = transcript_files[index]
    except (ValueError, IndexError):
        print("❌ Invalid selection.")
        return

    # Load paths
    map_path = os.path.join(SPEAKER_MAPS_DIR, selected_file)
    transcript_name = selected_file.replace(".json", ".txt")
    transcript_path = os.path.join(TRANSCRIPTS_DIR, transcript_name)
    labelled_path = os.path.join(LABELLED_TRANSCRIPTS_DIR, transcript_name)

    # Load map and transcript
    original_map = load_json(map_path)
    print(f"\n🎧 Reviewing: {transcript_name}")
    updated_map = edit_mapping(original_map)

    # Save updated per-file map
    save_json(map_path, updated_map)
    print("✅ Updated speaker map saved.")

    # Update global map
    global_map = update_global_map(global_map, updated_map, transcript_name)
    save_global_map(global_map)
    print("🌍 Global speaker map updated.")

    # Regenerate relabelled transcript
    text = load_text(transcript_path)
    relabelled = relabel_transcript(text, updated_map)
    save_text(labelled_path, relabelled)
    print(f"📄 Relabelled transcript saved to {labelled_path}")

if __name__ == "__main__":
    main()
