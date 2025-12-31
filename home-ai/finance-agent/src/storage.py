"""SQLite storage for transactions and merchant intelligence dictionary."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import json

DB_PATH = Path(
    os.environ.get(
        "FINANCE_DB_PATH", str(Path(__file__).parent.parent / "data" / "finance.db")
    )
)


@dataclass
class Transaction:
    id: Optional[int]
    date: str
    description: str
    amount: float
    category: Optional[str]
    merchant: str
    user_id: str
    doc_id: Optional[str] = None


def init_db() -> sqlite3.Connection:
    """Initialize SQLite database with required schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            is_admin BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS merchant_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_name TEXT NOT NULL,
            normalized_name TEXT NOT NULL UNIQUE,
            category TEXT,
            confidence_score REAL DEFAULT 0.0,
            times_confirmed INTEGER DEFAULT 0,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (raw_name, category)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            doc_id TEXT,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT,
            merchant TEXT NOT NULL,
            raw_merchant TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Documents table to track uploads and metadata
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            filename TEXT,
            pages INTEGER,
            bytes INTEGER,
            upload_ts TEXT
        )
    """)

    # Analysis jobs table to track consent and job status
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_jobs (
            job_id TEXT PRIMARY KEY,
            doc_id TEXT UNIQUE,
            status TEXT,
            started_at TEXT,
            completed_at TEXT,
            error TEXT,
            consent_given INTEGER DEFAULT 0,
            confirmed_specialist TEXT,
            confirmed_intent TEXT,
            phinance_raw_response TEXT,
            phinance_sanitized TEXT
        )
    """)

    conn.commit()
    return conn


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch user record including admin status."""
    with get_db() as conn:
        user = conn.execute(
            "SELECT user_id, is_admin FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    if user:
        return dict(user)
    return None


def add_user(user_id: str, is_admin: bool = False) -> None:
    """Create new user household member."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, is_admin) VALUES (?, ?)",
            (user_id, is_admin),
        )
        conn.commit()


def upsert_merchant_mapping(
    raw_name: str,
    normalized_name: str,
    category: Optional[str],
    confidence: float = 0.0,
) -> int:
    """
    Insert or update merchant mapping.
    Returns the mapping ID.
    """
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO merchant_mappings
                (raw_name, normalized_name, category, confidence_score)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(raw_name, category) DO UPDATE SET
                confidence_score = excluded.confidence_score + 1,
                times_confirmed = times_confirmed + 1,
                last_seen = CURRENT_TIMESTAMP
        """,
            (raw_name, normalized_name, category, confidence),
        )

        conn.commit()
        return cursor.lastrowid


def get_merchant_mapping(
    raw_name: str, category: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch merchant mapping by raw name and optional category.
    Returns normalized name, category, and confidence score.
    """
    with get_db() as conn:
        if category:
            row = conn.execute(
                """
                SELECT normalized_name, category, confidence_score
                FROM merchant_mappings
                WHERE raw_name = ? AND category = ?
            """,
                (raw_name, category),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT normalized_name, category, confidence_score
                FROM merchant_mappings
                WHERE raw_name = ?
            """,
                (raw_name,),
            ).fetchone()

        if row:
            return {"normalized_name": row[0], "category": row[1], "confidence": row[2]}
    return None


def insert_transactions(
    user_id: str, transactions: List[Transaction], doc_id: Optional[str] = None
) -> None:
    """
    Insert batch of transactions for a user.
    Links each transaction to merchant mapping via raw_merchant field.
    """
    with get_db() as conn:
        for tx in transactions:
            tx_doc_id = tx.doc_id or doc_id
            conn.execute(
                """
                INSERT INTO transactions (user_id, doc_id, date, description, amount, category, merchant, raw_merchant)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    user_id,
                    tx_doc_id,
                    tx.date,
                    tx.description,
                    tx.amount,
                    tx.category,
                    tx.merchant,
                    tx.merchant,
                ),
            )
        conn.commit()


def get_transactions(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch transactions for user with pagination."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, doc_id, date, description, amount, category, merchant, created_at
            FROM transactions
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT ?
        """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_transactions_by_doc(doc_id: str) -> List[Dict[str, Any]]:
    """Fetch all transactions for a specific document."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, doc_id, user_id, date, description, amount, category, merchant, created_at
            FROM transactions
            WHERE doc_id = ?
            ORDER BY date ASC
        """,
            (doc_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def has_transactions_for_doc(doc_id: str) -> bool:
    """Check if transactions already exist for a document (avoids re-parsing)."""
    with get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE doc_id = ?", (doc_id,)
        ).fetchone()[0]
    return count > 0


def get_merchant_dictionary_stats() -> Dict[str, int]:
    """Get statistics on merchant dictionary coverage."""
    with get_db() as conn:
        total = conn.execute("""
            SELECT COUNT(DISTINCT raw_name) FROM merchant_mappings
        """).fetchone()[0]
        high_conf = conn.execute("""
            SELECT COUNT(*) FROM merchant_mappings
            WHERE confidence_score >= 3.0
        """).fetchone()[0]

        return {"total_merchants": total, "high_confidence": high_conf}


# -----------------------------
# Analysis jobs and documents
# -----------------------------
def create_analysis_job(job_id: str, doc_id: str, status: str = "pending") -> None:
    """Create or update an analysis job record."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO analysis_jobs(job_id, doc_id, status, started_at) VALUES(?,?,?,?)",
            (job_id, doc_id, status, datetime.utcnow().isoformat()),
        )
        conn.commit()


def update_analysis_job(job_id: str, **fields) -> None:
    """Update analysis_jobs table fields (allowed set)."""
    allowed = {
        "status",
        "started_at",
        "completed_at",
        "error",
        "phinance_raw_response",
        "phinance_sanitized",
        "consent_given",
        "confirmed_specialist",
        "confirmed_intent",
    }
    updates = []
    params = []
    for k, v in fields.items():
        if k in allowed:
            updates.append(f"{k}=?")
            params.append(v)
    if not updates:
        return
    params.append(job_id)
    with get_db() as conn:
        conn.execute(
            f"UPDATE analysis_jobs SET {', '.join(updates)} WHERE job_id=?", params
        )
        conn.commit()


def get_pending_jobs() -> List[Dict[str, Any]]:
    """Return jobs that are pending or running."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM analysis_jobs WHERE status IN ('pending','running')"
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_jobs() -> List[Dict[str, Any]]:
    """Return all stored analysis jobs."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM analysis_jobs").fetchall()
        return [dict(r) for r in rows]


def save_transactions_for_doc(
    doc_id: str, transactions: List[Dict[str, Any]], user_id: str = "sachin"
) -> int:
    """Save parsed transactions for a document. Returns count of transactions saved."""
    tx_objs: List[Transaction] = []
    for tx in transactions:
        date = tx.get("date") or tx.get("date_raw") or ""
        description = tx.get("description") or tx.get("raw_line") or ""
        amount = tx.get("amount") or 0.0
        category = tx.get("category")
        merchant = tx.get("merchant") or tx.get("merchant_clean") or "Unknown"
        tx_objs.append(
            Transaction(
                id=None,
                date=date,
                description=description,
                amount=float(amount),
                category=category,
                merchant=merchant,
                user_id=user_id,
                doc_id=doc_id,
            )
        )

    insert_transactions(user_id, tx_objs, doc_id=doc_id)
    return len(tx_objs)


# Alias for backward compatibility with main.py
save_transactions = save_transactions_for_doc


def load_job_by_doc_id(doc_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM analysis_jobs WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        return dict(row) if row else None


def load_job(job_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM analysis_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        return dict(row) if row else None


def save_analysis_job(job: Dict[str, Any]) -> None:
    """Upsert an analysis job record from a dict.

    Checks by doc_id first (since that's the UNIQUE constraint), then by job_id.
    This handles the case where different services create jobs with different job_ids
    for the same document.
    """
    job_id = job.get("job_id")
    doc_id = job.get("doc_id")
    if not job_id or not doc_id:
        return

    with get_db() as conn:
        # Check by doc_id first (UNIQUE constraint)
        existing = conn.execute(
            "SELECT job_id FROM analysis_jobs WHERE doc_id = ?", (doc_id,)
        ).fetchone()

        if existing:
            allowed = {
                "status",
                "started_at",
                "completed_at",
                "error",
                "phinance_raw_response",
                "phinance_sanitized",
                "consent_given",
                "confirmed_specialist",
                "confirmed_intent",
                "job_id",
            }
            updates = []
            params = []
            for k, v in job.items():
                if k in allowed:
                    updates.append(f"{k}=?")
                    params.append(v)
            if updates:
                params.append(doc_id)
                conn.execute(
                    f"UPDATE analysis_jobs SET {', '.join(updates)} WHERE doc_id=?",
                    params,
                )
        else:
            conn.execute(
                """INSERT INTO analysis_jobs(job_id, doc_id, status, consent_given, started_at)
                   VALUES(?, ?, ?, ?, ?)""",
                (
                    job_id,
                    doc_id,
                    job.get("status", "pending"),
                    job.get("consent_given", 0),
                    datetime.utcnow().isoformat(),
                ),
            )
        conn.commit()


def save_document(document_id: str, filename: str, pages: int, bytes_size: int) -> None:
    """Persist a document metadata record."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO documents(document_id, filename, pages, bytes, upload_ts) VALUES(?,?,?,?,?)",
            (document_id, filename, pages, bytes_size, datetime.utcnow().isoformat()),
        )
        conn.commit()
