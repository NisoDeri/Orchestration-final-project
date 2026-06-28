"""Project logging: a single, idempotently-configured logger for the package."""

import logging


def get_logger(name: str = "q20") -> logging.Logger:
    """Return a configured logger; safe to call repeatedly (handlers added once)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
