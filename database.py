import sqlite3
from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # safe concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS bills (
                id        TEXT PRIMARY KEY,
                title     TEXT,
                session   TEXT,
                added_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS actions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_id     TEXT    NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
                date        TEXT,
                chamber     TEXT,
                description TEXT,
                order_num   INTEGER,
                UNIQUE(bill_id, order_num)
            );
        """)
