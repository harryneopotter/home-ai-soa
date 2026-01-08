#!/usr/bin/env python3
"""
One-time cleanup script to remove duplicate transactions.
Run AFTER deploying the transaction duplication bug fix.

Bug: All transactions were saved to ALL doc_ids instead of their source doc_id.
Fix: Transactions now tagged with source doc_id during extraction.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("/home/ryzen/projects/home-ai/finance-agent/data/finance.db")


def main():
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)

    before = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    print(f"Transactions before: {before}")

    dupes_sample = conn.execute("""
        SELECT doc_id, date, merchant, amount, COUNT(*) as count 
        FROM transactions 
        GROUP BY doc_id, date, merchant, amount 
        HAVING count > 1
        LIMIT 5
    """).fetchall()

    if dupes_sample:
        print(f"\nSample duplicates found:")
        for d in dupes_sample:
            print(f"  {d}")
    else:
        print("\nNo duplicates found - database is clean!")
        conn.close()
        return

    conn.execute("""
        DELETE FROM transactions WHERE id NOT IN (
            SELECT MIN(id) FROM transactions 
            GROUP BY doc_id, date, merchant, amount
        )
    """)
    conn.commit()

    after = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    print(f"\nTransactions after: {after}")
    print(f"Removed {before - after} duplicates")

    remaining = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT doc_id, date, merchant, amount
            FROM transactions 
            GROUP BY doc_id, date, merchant, amount 
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    print(f"Remaining duplicate groups: {remaining}")

    conn.close()


if __name__ == "__main__":
    main()
