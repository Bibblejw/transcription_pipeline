import json
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
from pydub import AudioSegment

from common import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

# Try to load Silero VAD via torch.hub. Fallback to webrtcvad if unavailable.
try:  # pragma: no cover - best effort import
    import torch

    silero_model, utils = torch.hub.load(
        "snakers4/silero-vad", "silero_vad", trust_repo=True
    )
    get_speech_timestamps, *_ = utils
    USE_SILERO = True
except Exception:  # pragma: no cover
    USE_SILERO = False
    torch = None
    import webrtcvad


def _detect_silero(audio: AudioSegment) -> List[Tuple[float, float]]:
    """Return raw speech timestamps using Silero VAD."""
    # Ensure 16 kHz mono
    audio = audio.set_frame_rate(16000).set_channels(1)
    samples = np.array(audio.get_array_of_samples()).astype(np.float32) / 32768.0
    tensor = torch.from_numpy(samples)
    timestamps = get_speech_timestamps(tensor, silero_model, sampling_rate=16000)
    return [(ts["start"] / 16000.0, ts["end"] / 16000.0) for ts in timestamps]


def _detect_webrtc(audio: AudioSegment) -> List[Tuple[float, float]]:
    """Return raw speech timestamps using webrtcvad."""
    audio = audio.set_frame_rate(16000).set_channels(1)
    sample_rate = audio.frame_rate
    vad = webrtcvad.Vad(2)
    frame_ms = 30
    frame_bytes = int(sample_rate * frame_ms / 1000) * audio.sample_width
    raw = audio.raw_data
    num_frames = len(raw) // frame_bytes
    segments: List[Tuple[float, float]] = []
    start = None
    frame_duration = frame_ms / 1000.0
    for i in range(num_frames):
        frame = raw[i * frame_bytes : (i + 1) * frame_bytes]
        is_speech = vad.is_speech(frame, sample_rate)
        t = i * frame_duration
        if is_speech:
            if start is None:
                start = t
        else:
            if start is not None:
                segments.append((start, t))
                start = None
    if start is not None:
        segments.append((start, num_frames * frame_duration))
    return segments


def _merge_segments(segments: List[Tuple[float, float]], max_gap: float = 0.2) -> List[Tuple[float, float]]:
    if not segments:
        return []
    merged = [segments[0]]
    for start, end in segments[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= max_gap:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return merged


def split_audio(input_path: Path, out_dir: Path, prefix: str | None = None) -> List[Tuple[float, float, Path]]:
    """Split ``input_path`` into speech segments using VAD.

    Returns a list of (start_sec, end_sec, segment_path).
    """
    audio = AudioSegment.from_file(input_path)
    duration = len(audio) / 1000.0
    raw_segments = _detect_silero(audio) if USE_SILERO else _detect_webrtc(audio)
    merged = _merge_segments(raw_segments)

    results: List[Tuple[float, float, Path]] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    base = prefix or input_path.stem
    for i, (start, end) in enumerate(merged):
        start_pad = max(0.0, start - 0.1)
        end_pad = min(duration, end + 0.1)
        segment_audio = audio[int(start_pad * 1000) : int(end_pad * 1000)]
        segment_path = out_dir / f"{base}_seg{i:03d}.wav"
        segment_audio.export(segment_path, format="wav")
        results.append((start_pad, end_pad, segment_path))
    return results


def main():
    if len(sys.argv) != 3:
        print("Usage: python vad_split.py <input.wav> <output_dir>")
        sys.exit(1)
    input_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    segments = split_audio(input_path, out_dir)
    sys.stdout.write(json.dumps([(s, e, str(p)) for s, e, p in segments]) + "\n")


if __name__ == "__main__":
    main()
