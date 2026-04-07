import sqlite3
import pytest
from unittest.mock import patch
from database import init_db, get_connection


def test_data_persists_across_connections(tmp_path):
    """Data written through one connection is readable through a fresh connection."""
    db_file = tmp_path / "test_tracker.db"

    with patch("database.DB_PATH", db_file):
        init_db()

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test Bill', '104th')"
            )

        # Open a second, independent connection to the same file
        conn2 = sqlite3.connect(db_file)
        conn2.row_factory = sqlite3.Row
        row = conn2.execute("SELECT * FROM bills WHERE id = 'HB1288'").fetchone()
        conn2.close()

    assert row is not None
    assert row["title"] == "Test Bill"


def test_cascade_delete_persists(tmp_path):
    """Deleting a bill also removes its actions on disk (foreign key cascade)."""
    db_file = tmp_path / "test_tracker.db"

    with patch("database.DB_PATH", db_file):
        init_db()

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test', '104th')"
            )
            conn.execute(
                "INSERT INTO actions (bill_id, date, chamber, description, order_num) "
                "VALUES ('HB1288', '2025-01-15', 'House', 'First reading', 1)"
            )

        with get_connection() as conn:
            conn.execute("DELETE FROM bills WHERE id = 'HB1288'")

        conn2 = sqlite3.connect(db_file)
        actions = conn2.execute(
            "SELECT * FROM actions WHERE bill_id = 'HB1288'"
        ).fetchall()
        conn2.close()

    assert len(actions) == 0
