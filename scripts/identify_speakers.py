import os
import re
import json
from dotenv import load_dotenv
from openai import OpenAI
from common import setup_logging, get_logger
from maintain_global_speakers import (
    load_global_map,
    save_global_map,
    update_global_map
)

# === Load environment ===
load_dotenv()
setup_logging()
logger = get_logger(__name__)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TRANSCRIPTS_DIR = os.getenv("TRANSCRIPTS")
SPEAKER_MAPS_DIR = os.getenv("SPEAKER_MAPS")
LABELLED_TRANSCRIPTS_DIR = os.getenv("TRANSCRIPTS_LABELLED")

client = OpenAI(api_key=OPENAI_API_KEY)

# === Helpers ===

def split_into_chunks(text, max_chars=6000):
    lines = text.splitlines()
    chunks = []
    current = ""

    for line in lines:
        if len(current) + len(line) + 1 > max_chars:
            chunks.append(current.strip())
            current = ""
        current += line + "\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks

def get_known_speakers(global_map, max_names=5):
    """Return a list of most recently seen speaker names."""
    entries = sorted(
        global_map.items(),
        key=lambda kv: kv[1].get("last_seen", ""),
        reverse=True
    )
    return [name for name, _ in entries[:max_names]]

def identify_speakers_from_text(text, global_map, max_chunks=3, chunk_size=6000):
    chunks = split_into_chunks(text, max_chars=chunk_size)
    chunks = chunks[:max_chunks]

    known_speakers = get_known_speakers(global_map)
    name_list = ", ".join(known_speakers) if known_speakers else "None"

    system_prompt = (
        "You are given a transcript of a conversation with generic speaker labels "
        "like 'Speaker 1', 'Speaker 2', etc. Based on greetings, phrasing, or role context, "
        "infer the most likely names or roles for each speaker. "
        "Respond ONLY with a JSON object mapping original labels to inferred names.\n\n"
        "You may assume 'Speaker 1' is often the user, Jozef, especially if leading the conversation.\n"
        f"Known frequent speaker names: {name_list}.\n"
    )

    aggregated_map = {}

    for i, chunk in enumerate(chunks):
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": chunk}
                ],
                temperature=0.3
            )
            result = json.loads(response.choices[0].message.content)

            for speaker, name in result.items():
                if speaker not in aggregated_map:
                    aggregated_map[speaker] = name
        except Exception:
            logger.exception(f"⚠️ GPT error in chunk {i + 1}")

    return aggregated_map

def relabel_transcript(text, speaker_map):
    for original, replacement in speaker_map.items():
        text = text.replace(f"{original}:", f"{replacement}:")
        text = text.replace(f"[{original}]", f"[{replacement}]")
    return text

def load_transcript(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def save_labelled_transcript(filename, labelled_text):
    path = os.path.join(LABELLED_TRANSCRIPTS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(labelled_text)

# === Main Processing ===

def main():
    os.makedirs(SPEAKER_MAPS_DIR, exist_ok=True)
    os.makedirs(LABELLED_TRANSCRIPTS_DIR, exist_ok=True)

    global_map = load_global_map()
    transcript_files = [f for f in os.listdir(TRANSCRIPTS_DIR) if f.endswith(".txt")]
    print(f"📂 Found {len(transcript_files)} transcripts to check.")

    for fname in transcript_files:
        txt_path = os.path.join(TRANSCRIPTS_DIR, fname)
        map_path = os.path.join(SPEAKER_MAPS_DIR, fname.replace(".txt", ".json"))
        labelled_path = os.path.join(LABELLED_TRANSCRIPTS_DIR, fname)

        try:
            text = load_transcript(txt_path)

            if os.path.exists(map_path):
                print(f"♻️ Reprocessing {fname} using existing speaker map...")
                with open(map_path, "r", encoding="utf-8") as f:
                    speaker_map = json.load(f)
            else:
                print(f"🧠 Inferring speakers for: {fname}")
                speaker_map = identify_speakers_from_text(text, global_map)
                save_json(map_path, speaker_map)
                global_map = update_global_map(global_map, speaker_map, fname)
                save_global_map(global_map)

            labelled_text = relabel_transcript(text, speaker_map)
            save_labelled_transcript(fname, labelled_text)
            print(f"✅ Output saved for {fname}")

        except Exception:
            logger.exception(f"❌ Failed to process {fname}")

if __name__ == "__main__":
    main()
