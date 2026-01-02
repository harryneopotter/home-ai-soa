"""Structured model call logging (JSONL) with optional redaction.

Writes append-only JSON lines to logs/model_calls.jsonl with restricted
file permissions (owner read/write only). Use log_model_call to record
model request/response pairs for observability and audit.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_PATH = LOG_DIR / "model_calls.jsonl"
LOG_DIR.mkdir(parents=True, exist_ok=True)
try:
    os.chmod(LOG_DIR, 0o700)
except Exception:
    pass


def _ensure_file():
    if not LOG_PATH.exists():
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("")
        try:
            os.chmod(LOG_PATH, 0o600)
        except Exception:
            pass


def _truncate(text: Optional[str], max_chars: int = 2000) -> str:
    if text is None:
        return ""
    t = str(text)
    return t if len(t) <= max_chars else t[:max_chars] + "... [truncated]"


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for linking request/response pairs."""
    return f"req-{uuid.uuid4().hex[:12]}"


def log_model_call(
    *,
    model_name: str,
    resolved_model: Optional[str],
    endpoint: str,
    prompt_source: str,
    prompt_type: str,
    prompt_text: Optional[str],
    options: Optional[Dict[str, Any]] = None,
    response_id: Optional[str] = None,
    response_text: Optional[str] = None,
    latency_ms: Optional[float] = None,
    status: str = "success",
    error: Optional[str] = None,
    redact: bool = True,
    correlation_id: Optional[str] = None,
    attempt: Optional[int] = None,
) -> None:
    """Append a structured JSON line describing a model call.

    Args:
        correlation_id: Unique ID to link request/response pairs
        attempt: Attempt number for retry scenarios (1-based)
        redact: when True, redact sensitive prompt_text (only store hash & truncated preview)
    """
    _ensure_file()

    prompt_preview = _truncate(prompt_text, 2000)
    prompt_hash = hashlib.sha256((prompt_text or "").encode("utf-8")).hexdigest()

    if redact:
        prompt_preview = _truncate(prompt_text, 200)

    entry = {
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "correlation_id": correlation_id,
        "attempt": attempt,
        "model_name": model_name,
        "resolved_model": resolved_model,
        "endpoint": endpoint,
        "prompt_source": prompt_source,
        "prompt_type": prompt_type,
        "prompt_preview": prompt_preview,
        "prompt_hash": prompt_hash,
        "options": options or {},
        "response_id": response_id,
        "response_preview": _truncate(response_text, 1000) if response_text else None,
        "latency_ms": latency_ms,
        "status": status,
        "error": error,
    }

    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
