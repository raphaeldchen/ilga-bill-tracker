"""
One-time script: copy all data from local SQLite database to Supabase.

Usage:
    python -m scripts.sqlite_to_supabase

Reads from:  data/tracker.db  (local SQLite file)
Writes to:   DATABASE_URL      (Supabase Postgres, from .env)

Safe to re-run — uses ON CONFLICT DO NOTHING on both tables.
"""

import sys
import sqlite3
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from config import DATABASE_URL, DB_PATH


async def main() -> None:
    if not DB_PATH.exists():
        print(f"No local database found at {DB_PATH}. Nothing to migrate.")
        return

    if not DATABASE_URL:
        print("DATABASE_URL is not set. Check your .env file.")
        sys.exit(1)

    sqlite_conn = sqlite3.connect(DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    pg_conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)

    bills = sqlite_conn.execute("SELECT * FROM bills").fetchall()
    print(f"Migrating {len(bills)} bills...")
    await pg_conn.executemany(
        "INSERT INTO bills (id, title, session, added_at, last_fetched_at, note, source_url) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (id) DO NOTHING",
        [(b["id"], b["title"], b["session"], b["added_at"],
          b["last_fetched_at"], b["note"], b["source_url"]) for b in bills],
    )

    actions = sqlite_conn.execute("SELECT * FROM actions").fetchall()
    print(f"Migrating {len(actions)} actions...")
    await pg_conn.executemany(
        "INSERT INTO actions (bill_id, date, chamber, description, order_num) "
        "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (bill_id, order_num) DO NOTHING",
        [(a["bill_id"], a["date"], a["chamber"], a["description"], a["order_num"])
         for a in actions],
    )

    sqlite_conn.close()
    await pg_conn.close()
    print(f"Done. Migrated {len(bills)} bills and {len(actions)} actions.")


if __name__ == "__main__":
    asyncio.run(main())
