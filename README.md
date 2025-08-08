# Transcription Pipeline

## Setup

You can bootstrap your local environment (create the venv, install dependencies, and copy your .env) by running:

```bash
./init_env.sh
```

# Requirements

- Python 3.11 is required; running on other Python versions may lead to dependency errors (e.g., numba incompatibility).

Copy the example config file and fill in the environment variables:

```bash
cp .env.example .env
```

Create and activate a Python virtual environment (using Python 3.11):

```bash
python3.11 -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\\Scripts\\activate    # Windows PowerShell
```

## Installation

Install the required Python packages (including OpenAI Whisper for transcription):

```bash
pip install -r requirements.txt
```

## Configuration

Refer to [docs/icloud_sync.md](docs/icloud_sync.md) for instructions on syncing Just Press Record recordings from iCloud Drive.

### Database initialization

Before queuing jobs or running the dashboard, initialize the SQLite schema by running:

```bash
python3 scripts/init_db.py
```

This will create `transcripts.db` (or the file specified by `TRANSCRIPTS_DB` in your `.env`) with the required tables.

## Docker

To run the full pipeline in containers, build the image and start the stack with Docker Compose. Create host directories for audio input, audio segments, and the database, then run:

```bash
docker-compose up -d
```

The service mounts the following paths by default (override in `docker-compose.yml`):

* `./audio` → `/mnt/audio`
* `./audio_segments` → `/mnt/audio_segments`
* `./db` → `/mnt/db`

Place recordings into the mounted audio directory and they will be processed automatically. Visit the dashboard at [http://localhost:8000/dashboard](http://localhost:8000/dashboard).


## Running the API

Start the FastAPI server:

```bash
uvicorn app:app --reload
```

### Health Check

After the server is running, verify the API is responsive:

```bash
# Expect an empty list or existing recordings
curl http://127.0.0.1:8000/api/recordings
```

### Summarize Recordings

Generate and store an LLM-based summary for a specific recording by its ID:

```bash
# Trigger summarization and save to the database
curl -X POST http://127.0.0.1:8000/api/recordings/1/summarize
```

Retrieve a previously saved summary for a recording:

```bash
curl http://127.0.0.1:8000/api/recordings/1/summary
```
=======
## Running Monitoring and Dashboard Together

> **Note:** Before running the monitoring and dashboard together locally, ensure you've created and activated your Python virtual environment, installed dependencies with `pip install -r requirements.txt`, and copied `.env.example` to `.env`.

To run the file monitor alongside the dashboard server, use the helper script:

```bash
python scripts/start_services.py
```

This launches the monitoring loop and the FastAPI dashboard in one step.
