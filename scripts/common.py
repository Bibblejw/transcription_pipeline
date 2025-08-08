import sys
from pathlib import Path

# Ensure the repository root is on the Python path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from logging_config import setup_logging, get_logger  # noqa: E402
