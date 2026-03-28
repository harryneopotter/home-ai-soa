import sqlite3
import json
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

from orchestrator import Capability

logger = logging.getLogger(__name__)


DB_PATH = Path(__file__).resolve().parent.parent / "soa1.db"


@dataclass
class CapabilityConsentRecord:
    session_id: str
    capability: Capability
    granted_at: datetime


@dataclass
class InvocationApprovalRecord:
    session_id: str
    batch_id: str
    specialist: str
    granted_at: datetime


class ConsentManager:
    def __init__(self) -> None:
        self._ensure_schema()

    @contextmanager
    def _conn(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            yield conn

    def _ensure_schema(self) -> None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS capability_consents (
                    session_id TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    granted_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, capability)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS invocation_approvals (
                    session_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    specialist TEXT NOT NULL,
                    granted_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, batch_id, specialist)
                )
            """)
            conn.commit()

    def grant_capability(self, session_id: str, capability: Capability) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO capability_consents(session_id, capability, granted_at) VALUES (?,?,?)",
                (session_id, capability.value, datetime.utcnow().isoformat()),
            )
            conn.commit()
            logger.debug(
                "Granted capability %s to session %s", capability.value, session_id
            )

    def has_capability(self, session_id: str, capability: Capability) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM capability_consents WHERE session_id=? AND capability=?",
                (session_id, capability.value),
            ).fetchone()
            return row is not None

    def grant_invocation_approval(
        self, session_id: str, batch_id: str, specialist: str
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO invocation_approvals(session_id, batch_id, specialist, granted_at) VALUES (?,?,?,?)",
                (session_id, batch_id, specialist, datetime.utcnow().isoformat()),
            )
            conn.commit()
            logger.debug(
                "Granted invocation approval %s/%s/%s", session_id, batch_id, specialist
            )

    def has_invocation_approval(
        self, session_id: str, batch_id: str, specialist: str
    ) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM invocation_approvals WHERE session_id=? AND batch_id=? AND specialist=?",
                (session_id, batch_id, specialist),
            ).fetchone()
            return row is not None

    def attach_legacy_fallback(self, loader) -> None:
        self._legacy_loader = loader

    def has_legacy_consent(self, job_id: str) -> bool:
        if not hasattr(self, "_legacy_loader"):
            return False
        job = self._legacy_loader(job_id)
        return bool(job and job.get("consent_given"))
