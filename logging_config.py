import logging
import sys

def setup_logging(level=logging.INFO):
    # Log to stdout and to a file for persistent exception traces
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("app.log", encoding="utf-8"),
        ],
    )
