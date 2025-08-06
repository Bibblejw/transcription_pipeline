import os
import json
import logging
import builtins
from dotenv import load_dotenv
from openai import OpenAI
from logging_config import setup_logging

# === Load environment ===
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LABELLED_DIR = os.getenv("TRANSCRIPTS_LABELLED")
SUMMARY_DIR = os.getenv("SUMMARIES")

client = OpenAI(api_key=OPENAI_API_KEY)
setup_logging()
builtins.print = lambda *args, **kwargs: logging.getLogger(__name__).info(" ".join(str(a) for a in args), **kwargs)
logger = logging.getLogger(__name__)

# === Parameters ===
CHUNK_SIZE = 7000  # characters
MAX_CHUNKS = 5     # configurable if you want deeper coverage

# === Utility Functions ===

def split_text_into_chunks(text, max_chars=CHUNK_SIZE):
    lines = text.splitlines()
    chunks, current = [], ""

    for line in lines:
        if len(current) + len(line) + 1 > max_chars:
            chunks.append(current.strip())
            current = ""
        current += line + "\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks

def list_transcripts_to_process():
    return [
        f for f in os.listdir(LABELLED_DIR)
        if f.endswith(".txt") and not os.path.exists(os.path.join(SUMMARY_DIR, f.replace(".txt", ".md")))
    ]

def load_transcript(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def save_summary(filename, content):
    out_path = os.path.join(SUMMARY_DIR, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

# === GPT Prompt ===

def summarise_chunk(chunk):
    system_prompt = (
        "You are an assistant tasked with summarising conversations.\n"
        "The transcript is labelled with real speaker names like 'Jozef' or 'Alex'.\n"
        "Your job is to:\n"
        "- Identify whether the conversation is Work or Personal.\n"
        "- Provide a bullet-point list of actions, decisions, or things to remember.\n"
        "- Write a concise natural language summary."
    )

    user_prompt = (
        "Here is the transcript chunk:\n\n"
        + chunk
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.5
    )

    return response.choices[0].message.content.strip()

# === Main Function ===

def main():
    os.makedirs(SUMMARY_DIR, exist_ok=True)
    files = list_transcripts_to_process()

    print(f"📝 Found {len(files)} transcript(s) to summarise.")

    for fname in files:
        path = os.path.join(LABELLED_DIR, fname)
        print(f"\n📄 Processing: {fname}")

        try:
            raw_text = load_transcript(path)
            chunks = split_text_into_chunks(raw_text)
            chunks = chunks[:MAX_CHUNKS]

            all_summaries = []
            for i, chunk in enumerate(chunks):
                print(f"   ✂️  Summarising chunk {i + 1}/{len(chunks)}...")
                summary = summarise_chunk(chunk)
                all_summaries.append(summary)

            # Stitch summaries with context
            final_summary = "\n\n---\n\n".join(all_summaries)

            # Optional metadata block
            tag_line = "[Tag: Work or Personal — to be confirmed by review]"
            meta = f"""---
file: {fname}
tag: {tag_line}
chunks: {len(chunks)}
---

"""

            full_output = meta + final_summary
            save_summary(fname.replace(".txt", ".md"), full_output)
            print("   ✅ Summary saved.")

        except Exception:
            logger.exception(f"❌ Failed on {fname}")

if __name__ == "__main__":
    main()
