import sqlite3
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app

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
    Calls the real init_db() with both connection targets patched so
    tests always use the same schema as production.
    """
    from database import init_db
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    with patch("database.get_connection", return_value=conn), \
         patch("services.bills.get_connection", return_value=conn):
        init_db()
        yield conn
    conn.close()


@pytest.fixture
def client(db):
    """
    FastAPI TestClient with in-memory DB.
    The db fixture already patches both get_connection targets.
    """
    with TestClient(app) as c:
        yield c
