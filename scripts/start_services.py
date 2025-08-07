import subprocess
import sys
import logging
import builtins
from pathlib import Path
from common import setup_logging

setup_logging()
builtins.print = lambda *args, **kwargs: logging.getLogger(__name__).info(" ".join(str(a) for a in args), **kwargs)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]


def main():
    processes = []
    try:
        monitor_cmd = [sys.executable, str(ROOT / "scripts" / "monitor.py")]
        dashboard_cmd = ["uvicorn", "app:app", "--reload"]

        logger.info("Starting monitor...")
        processes.append(
            subprocess.Popen(monitor_cmd, cwd=ROOT / "scripts")
        )

        logger.info("Starting dashboard server...")
        processes.append(subprocess.Popen(dashboard_cmd, cwd=ROOT))

        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        logger.info("Shutting down services...")
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
        for p in processes:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
