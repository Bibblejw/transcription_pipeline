
## TASK LIST

- [todo] Integrate Silero VAD as a preprocessor for segmenting speaker-separated audio streams
- [todo] Implement Demucs speaker separation and store output in a temporary folder structure
- [todo] Create a new table in the database: `local_speakers`, linked to each recording
- [todo] Link local speaker objects to global speakers using resemblyzer-based embedding matching
- [todo] Implement script to generate a merged, chronologically ordered transcript from snippets
- [todo] Build manual override script for inspecting and updating `global_speakers` matches
- [todo] Add database migrations for recordings, snippets, local_speakers, and global_speakers
- [todo] Configure audio segment cache and cleanup routine after transcription completes
- [todo] Add logging and error handling to the speaker-mapping stage
