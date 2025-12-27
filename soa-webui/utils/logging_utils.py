"""Centralized logging utilities with redaction and rotating handlers.

This module provides:
- RedactingFormatter: masks sensitive patterns (credit cards, SSNs, emails) in log output
- setup_logging(service_name, ...): idempotently sets up rotating file + console handlers

Defaults:
- MONITOR_LOG_DIR environment variable controls where logs are stored
- Default log dir: <repo-root>/soa-webui/logs
- Default rotation: 5 MB / 5 backups

Security: Masking runs at formatting time so raw sensitive text is never written to disk.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Compile common sensitive patterns
# Credit-card-like: 13-16 digits, allowing separators (spaces/dashes)
_CC_RE = re.compile(r"\b(?:\d[ \-]*?){13,16}\b")
# SSN formats: 123-45-6789 or 9-digit
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b")
# Email addresses
_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", re.I)


def _mask_cc(m: re.Match) -> str:
    s = m.group(0)
    digits = re.sub(r"\D", "", s)
    if len(digits) <= 4:
        return "****"
    return "****" + digits[-4:]


def _mask_ssn(m: re.Match) -> str:
    s = m.group(0)
    digits = re.sub(r"\D", "", s)
    # return ***-**-1234 style
    return "***-**-" + digits[-4:]


def _mask_email(m: re.Match) -> str:
    local, domain = m.group(1), m.group(2)
    if not local:
        return "***@" + domain
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return masked_local + "@" + domain


def sanitize_text(s: Optional[str]) -> Optional[str]:
    """Return a sanitized copy of s where sensitive patterns are masked."""
    if s is None:
        return s
    try:
        # Emails first (so '@' doesn't interfere with other patterns)
        s = _EMAIL_RE.sub(_mask_email, s)
        s = _CC_RE.sub(_mask_cc, s)
        s = _SSN_RE.sub(_mask_ssn, s)
        return s
    except Exception:
        # In the unlikely case of an error in sanitization, fail-safe: return original
        return s


class RedactingFormatter(logging.Formatter):
    """Formatter that redacts sensitive material from the formatted message."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        sanitized = sanitize_text(formatted)
        return sanitized


def setup_logging(
    service_name: str,
    log_dir: Optional[str] = None,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
    level: int = logging.INFO,
    console: bool = True,
) -> logging.Logger:
    """Idempotently configure logging for a service.

    - Writes logs to MONITOR_LOG_DIR/service_name.log by default.
    - Attaches a RedactingFormatter so sensitive material is masked before writing.
    """

    # Determine default project-root-aware log dir if not provided
    env_dir = os.environ.get("MONITOR_LOG_DIR")
    if log_dir:
        target_dir = Path(log_dir)
    elif env_dir:
        target_dir = Path(env_dir)
    else:
        # Project root is assumed to be two levels up from this utils module
        project_root = Path(__file__).resolve().parents[2]
        target_dir = project_root / "soa-webui" / "logs"

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Best-effort: if mkdir fails, fallback to a local logs dir
        target_dir = Path("./logs")
        target_dir.mkdir(parents=True, exist_ok=True)

    log_file = target_dir / f"{service_name}.log"

    logger = logging.getLogger(service_name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(level)

    fmt = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    formatter = RedactingFormatter(fmt)

    try:
        file_handler = RotatingFileHandler(
            str(log_file), maxBytes=max_bytes, backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        # If file handler cannot be created, continue with console-only logging
        pass

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Avoid double logging to root handlers
    logger.propagate = False

    # Expose chosen log_dir for callers that want to list available logs
    logger._monitor_log_dir = str(target_dir)

    return logger
