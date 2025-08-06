import os
import logging
import builtins
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from logging_config import setup_logging

# === Load environment ===
load_dotenv()
setup_logging()
builtins.print = lambda *args, **kwargs: logging.getLogger(__name__).info(" ".join(str(a) for a in args), **kwargs)
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("WORK_EMAIL")
LABELLED_DIR = os.getenv("TRANSCRIPTS_LABELLED")
SUMMARY_DIR = os.getenv("SUMMARIES")

# === Helpers ===

def parse_summary_file(summary_path):
    with open(summary_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract tag from metadata
    tag_line = next((line for line in content.splitlines() if line.lower().startswith("tag:")), "tag: Unknown")
    tag = tag_line.split(":", 1)[1].strip().lower()

    # Extract first non-meta summary text for précis
    summary_lines = [line for line in content.splitlines() if line.strip() and not line.startswith("---") and not line.lower().startswith("tag:")]
    summary_body = "\n".join(summary_lines)
    praci = summary_body.split("\n\n")[0].strip()  # first paragraph or block
    return tag, praci, summary_body

def load_transcript(labelled_path):
    with open(labelled_path, "r", encoding="utf-8") as f:
        return f.read()

def send_transcript_email(filename):
    summary_path = os.path.join(SUMMARY_DIR, filename.replace(".txt", ".md"))
    labelled_path = os.path.join(LABELLED_DIR, filename)

    if not os.path.exists(summary_path) or not os.path.exists(labelled_path):
        logger.error(f"❌ Missing summary or transcript for {filename}")
        return

    tag, praci, summary = parse_summary_file(summary_path)

    if tag != "work":
        logger.warning(f"⚠️ Skipping non-work transcript: {filename}")
        return

    transcript = load_transcript(labelled_path)

    msg = EmailMessage()
    msg["Subject"] = f"[Transcript Summary] {filename} – Work"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    msg.set_content(
        f"""Summary Précis:
{praci}

---

📌 Full Summary:
{summary}

---

📄 Full Transcript:
{transcript}
"""
    )

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)

    logger.info(f"✅ Email sent for: {filename}")

# === Entry ===

def main():
    files = [f for f in os.listdir(SUMMARY_DIR) if f.endswith(".md")]

    for f in files:
        txt_name = f.replace(".md", ".txt")
        send_transcript_email(txt_name)

if __name__ == "__main__":
    main()
