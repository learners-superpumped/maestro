"""Structured logging setup for the Maestro orchestration daemon."""

from __future__ import annotations

import logging
import pathlib
import sys

from maestro.config import LoggingConfig

_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S"


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """Configure and return the 'maestro' logger.

    Args:
        config: Logging configuration with ``level`` and ``file`` fields.

    Returns:
        The configured :class:`logging.Logger` named ``"maestro"``.
    """
    logger = logging.getLogger("maestro")
    logger.setLevel(config.level.upper())

    # Clear any existing handlers to avoid duplicate output on re-init.
    logger.handlers.clear()

    formatter = logging.Formatter(fmt=_FORMAT, datefmt=_DATEFMT)

    # Console handler (stderr).
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler — create parent directories if they don't exist.
    log_path = pathlib.Path(config.file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
