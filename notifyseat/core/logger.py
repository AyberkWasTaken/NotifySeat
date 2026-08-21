"""Logging configuration for NotifySeat."""
import logging
import sys
from typing import Optional

try:
    from rich.logging import RichHandler
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def setup_logger(name: str = "notifyseat", level: int = logging.INFO) -> logging.Logger:
    """Set up and return the application logger."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        if HAS_RICH:
            handler = RichHandler(
                rich_tracebacks=True,
                show_time=True,
                show_path=False,
                markup=True
            )
        else:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger


logger = setup_logger()
