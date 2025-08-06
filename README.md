# Transcription Pipeline

## Setup

Copy the example config file and fill in the environment variables:

```bash
cp .env.example .env
```

Create and activate a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\\Scripts\\activate    # Windows PowerShell
```

## Installation

Install the required Python packages:

```bash
pip install -r requirements.txt
```

## Configuration

Refer to [docs/icloud_sync.md](docs/icloud_sync.md) for instructions on syncing Just Press Record recordings from iCloud Drive.

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
