from __future__ import annotations

import logging
from typing import Any

_LOGGER_NAME = 'maxiv_panda'


def configure_console_logging(level: int = logging.WARNING) -> logging.Logger:
    """Configure lightweight console logging for development diagnostics."""
    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('[%(name)s] %(levelname)s: %(message)s'))
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def get_logger() -> logging.Logger:
    return configure_console_logging()


def log_noncritical_error(context: str, exc: BaseException, *, logger: logging.Logger | None = None) -> None:
    target = logger or get_logger()
    target.warning('%s: %s', context, exc)


def log_debug(message: str, *args: Any, logger: logging.Logger | None = None) -> None:
    target = logger or get_logger()
    target.debug(message, *args)
