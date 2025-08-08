# Demucs Source Separation

This document describes how to run source separation on meeting audio using Demucs.

## Installation

Install Demucs and dependencies (requires Python 3.8+):

```bash
pip install demucs pyyaml
```

## Usage

Use the provided script to separate audio into per-speaker WAV files:

```bash
python scripts/demucs_run.py \
  --config config/demucs.yaml \
  input_audio.wav \
  output_directory
```

The script writes separated WAVs into `output_directory` and emits a `metadata.yaml` file with basic run information.

## VAD-based Segmentation

After you have separated audio into per-speaker streams, you can segment each stream into speech-only chunks using Silero VAD:

```bash
python scripts/vad_split.py \
  --input-dir output_directory \
  --output-dir vad_segments \
  # optional: force model reload
  # --reload-model
```

This will produce WAV files in `vad_segments` named like `<speaker>_segNNN.wav`, where each file contains a detected speech segment.
