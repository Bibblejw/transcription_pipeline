import logging
import sys
from pathlib import Path
import builtins

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


def get_logger(name: str) -> logging.Logger:
    """Return a module-specific logger and redirect ``print`` to it.

    The custom ``print`` discards unsupported keyword arguments such as
    ``file`` that the ``logging`` module does not accept.
    """

    logger = logging.getLogger(name)

    def log_print(*args, **kwargs):
        # ``traceback.print_exception`` passes ``file`` and ``end`` arguments;
        # they are not recognised by ``logger.info`` so remove them.
        kwargs.pop("file", None)
        sep = kwargs.pop("sep", " ")
        end = kwargs.pop("end", "")
        message = sep.join(str(a) for a in args) + end
        logger.info(message)

    builtins.print = log_print
    return logger
