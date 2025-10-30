"""Logging utilities for the NBA Pace Pulse project."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import SETTINGS, ensure_data_dir

_LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


def configure_logging() -> None:
    """Configure application-wide logging."""

    logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)
    if SETTINGS.feature_betting_insight:
        ensure_data_dir()
        log_dir = SETTINGS.data_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "app.log", maxBytes=2_000_000, backupCount=2
        )
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logging.getLogger().addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
