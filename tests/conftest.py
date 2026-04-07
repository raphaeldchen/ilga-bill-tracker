import sqlite3
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app

SCHEMA = """
CREATE TABLE IF NOT EXISTS bills (
    id              TEXT PRIMARY KEY,
    title           TEXT,
    session         TEXT,
    added_at        TEXT DEFAULT (datetime('now')),
    last_fetched_at TEXT
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
"""

# Reusable fake bill payload — mirrors what OpenStates returns for a real bill
FAKE_BILL = {
    "title": "TEST BILL",
    "session": "104th",
    "actions": [
        {
            "date": "2025-01-15",
            "description": "First reading",
            "order": 1,
            "organization": {"classification": "lower", "name": "House"},
        }
    ],
}


@pytest.fixture
def db():
    """
    Fresh in-memory SQLite DB per test.
    Patches services.bills.get_connection so all service calls use this connection.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    with patch("services.bills.get_connection", return_value=conn):
        yield conn
    conn.close()


@pytest.fixture
def client(db):
    """
    FastAPI TestClient with in-memory DB.
    Extends db fixture and also patches database.get_connection so that
    init_db() (called during app lifespan startup) uses the same in-memory DB.
    """
    with patch("database.get_connection", return_value=db):
        with TestClient(app) as c:
            yield c
