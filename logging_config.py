import logging
import sys
from pathlib import Path

def setup_logging(level=logging.INFO):
    # Log to stdout and to a file for persistent exception traces
    log_file = Path(__file__).parent / "app.log"
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(log_file), encoding="utf-8"),
        ],
    )
