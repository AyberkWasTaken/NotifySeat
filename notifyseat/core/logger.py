"""Logging configuration for NotifySeat."""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

try:
    from rich.logging import RichHandler
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

LOG_DIR = Path.home() / ".notifyseat"
LOG_FILE = LOG_DIR / "notifyseat.log"


def setup_logger(name: str = "notifyseat", level: int = logging.INFO) -> logging.Logger:
    """Set up and return the application logger with both terminal and persistent file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        # 1. Console Handler
        if HAS_RICH:
            console_handler = RichHandler(
                rich_tracebacks=True,
                show_time=True,
                show_path=False,
                markup=True
            )
        else:
            console_handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 2. Persistent Developer File Handler (~/.notifyseat/notifyseat.log)
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                str(LOG_FILE),
                maxBytes=5 * 1024 * 1024,  # 5MB per log file
                backupCount=3,
                encoding="utf-8"
            )
            file_formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception:
            pass
        
    return logger


logger = setup_logger()
