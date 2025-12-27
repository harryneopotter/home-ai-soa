import logging
import sys
import os
from logging.handlers import RotatingFileHandler


def get_logger(name: str, level=logging.INFO) -> logging.Logger:
    """Get a configured logger for soa1 services.

    This function delegates to the centralized setup_logging utility which
    configures rotating file handlers and redaction. It keeps backward
    compatibility for callers that expect a simple get_logger API.
    """
    try:
        # Prefer the local centralized logging utility when available
        from .logging_utils import setup_logging

        logger = setup_logging(name, level=level, console=True)
        return logger
    except Exception:
        # Fallback to a minimal logger if the centralized utility is not importable
        logger = logging.getLogger(name)
        if logger.handlers:
            return logger  # already configured

        logger.setLevel(level)

        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)

        # Add file handler with rotation for persistent logging
        file_handler = RotatingFileHandler(
            f"logs/{name}.log",
            maxBytes=1024 * 1024,  # 1MB per file
            backupCount=5,  # Keep 5 backup files
        )
        file_handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        )
        logger.addHandler(file_handler)

        # Add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        )
        logger.addHandler(console_handler)

        return logger
