import os
import json
from datetime import datetime
import logging
import builtins
from logging_config import setup_logging

GLOBAL_MAP_PATH = "global_speakers.json"

setup_logging()
builtins.print = lambda *args, **kwargs: logging.getLogger(__name__).info(" ".join(str(a) for a in args), **kwargs)
logger = logging.getLogger(__name__)

def load_global_map():
    if os.path.exists(GLOBAL_MAP_PATH):
        with open(GLOBAL_MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_global_map(global_map):
    with open(GLOBAL_MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(global_map, f, indent=2)

def extract_timestamp_from_filename(filename):
    # Example: 2025-08-03_14-18-00.txt → datetime
    stem = os.path.splitext(os.path.basename(filename))[0]
    try:
        return datetime.strptime(stem, "%Y-%m-%d_%H-%M-%S")
    except ValueError:
        return None

def update_global_map(global_map, local_map, filename):
    """
    - global_map: dict loaded from global_speakers.json
    - local_map: dict like {"Speaker 1": "Jozef", "Speaker 2": "Alex"}
    - filename: full filename of the current transcript
    """
    timestamp = extract_timestamp_from_filename(filename)
    iso_timestamp = timestamp.isoformat() if timestamp else None
    transcript_id = os.path.splitext(os.path.basename(filename))[0]

    for original_label, inferred_name in local_map.items():
        if inferred_name not in global_map:
            # New speaker entirely
            global_map[inferred_name] = {
                "aliases": [original_label],
                "first_seen": iso_timestamp,
                "last_seen": iso_timestamp,
                "transcripts": [transcript_id],
                "notes": ""
            }
        else:
            speaker = global_map[inferred_name]
            if original_label not in speaker["aliases"]:
                speaker["aliases"].append(original_label)
            if transcript_id not in speaker["transcripts"]:
                speaker["transcripts"].append(transcript_id)
            if timestamp:
                if "first_seen" not in speaker or timestamp < datetime.fromisoformat(speaker["first_seen"]):
                    speaker["first_seen"] = iso_timestamp
                if "last_seen" not in speaker or timestamp > datetime.fromisoformat(speaker["last_seen"]):
                    speaker["last_seen"] = iso_timestamp

    return global_map
