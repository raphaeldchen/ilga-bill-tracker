# Pre-Deploy Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four automated tests (export endpoint, DB persistence, migration, concurrent fetch) and one manual API check script to verify system correctness before deployment.

**Architecture:** New tests follow the existing conftest.py fixture pattern — in-memory SQLite via `db` fixture, mocked `fetch_bills` via `AsyncMock`. DB persistence tests intentionally bypass the mock and use real file-based connections via a patched `database.DB_PATH`. The API check script uses `httpx` (already a project dependency).

**Tech Stack:** pytest, pytest-asyncio, unittest.mock, httpx, Python stdlib (csv, sqlite3, asyncio)

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `tests/test_routes.py` | Add export endpoint test |
| Create | `tests/test_persistence.py` | File-based SQLite persistence tests |
| Create | `tests/test_migrate.py` | URL parsing + CSV import tests |
| Create | `tests/test_concurrent.py` | Concurrent fetch correctness test |
| Create | `scripts/check_api.py` | Manual real-API health check script |

---

## Task 1: Export endpoint test

**Files:**
- Modify: `tests/test_routes.py`

- [ ] **Step 1: Append export test to `tests/test_routes.py`**

Add this at the end of the file:

```python
def test_export_actions(client, db):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Bill A', '104th')")
        db.execute("INSERT INTO bills (id, title, session) VALUES ('SB0019', 'Bill B', '104th')")
        db.execute("INSERT INTO actions (bill_id, date, chamber, description, order_num) VALUES ('HB1288', '2025-01-15', 'House', 'First reading', 1)")
        db.execute("INSERT INTO actions (bill_id, date, chamber, description, order_num) VALUES ('SB0019', '2025-01-16', 'Senate', 'First reading', 1)")

    res = client.get("/api/actions/export")
    assert res.status_code == 200
    assert "attachment" in res.headers["content-disposition"]
    assert "legislative_tracker_updates.json" in res.headers["content-disposition"]
    data = res.json()
    assert len(data) == 2
    bill_ids = {a["bill_id"] for a in data}
    assert bill_ids == {"HB1288", "SB0019"}
```

- [ ] **Step 2: Run the test**

```bash
cd /Users/raphaelchen/Desktop/ilga_tracker && source .venv/bin/activate && pytest tests/test_routes.py::test_export_actions -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd /Users/raphaelchen/Desktop/ilga_tracker && git add tests/test_routes.py && git commit -m "test: add export endpoint test"
```

---

## Task 2: DB persistence tests

**Files:**
- Create: `tests/test_persistence.py`

**Context:** These tests use real file-based SQLite connections (not the in-memory `db` fixture). They patch `database.DB_PATH` so `get_connection()` writes to a temp file instead of `data/tracker.db`. This proves data survives connection close/reopen and that cascade deletes work on disk.

- [ ] **Step 1: Create `tests/test_persistence.py`**

```python
import sqlite3
import pytest
from unittest.mock import patch
from database import init_db, get_connection


def test_data_persists_across_connections(tmp_path):
    """Data written through one connection is readable through a fresh connection."""
    db_file = tmp_path / "test_tracker.db"

    with patch("database.DB_PATH", db_file):
        init_db()

        # Write data through first connection
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

        # Read from a fresh connection
        conn2 = sqlite3.connect(db_file)
        actions = conn2.execute(
            "SELECT * FROM actions WHERE bill_id = 'HB1288'"
        ).fetchall()
        conn2.close()

    assert len(actions) == 0
```

- [ ] **Step 2: Run the tests**

```bash
cd /Users/raphaelchen/Desktop/ilga_tracker && source .venv/bin/activate && pytest tests/test_persistence.py -v
```

Expected: 2 passed

- [ ] **Step 3: Commit**

```bash
cd /Users/raphaelchen/Desktop/ilga_tracker && git add tests/test_persistence.py && git commit -m "test: add DB persistence tests"
```

---

## Task 3: Real API check script

**Files:**
- Create: `scripts/check_api.py`

- [ ] **Step 1: Create `scripts/check_api.py`**

```python
#!/usr/bin/env python3
"""
Manual API health check — run after daily quota resets to verify the full
OpenStates integration end-to-end.

Requires the server to be running:
    uvicorn main:app --reload

Usage:
    source .venv/bin/activate && python scripts/check_api.py
"""

import sys
import httpx

BASE_URL = "http://127.0.0.1:8000"


def main() -> int:
    print(f"Connecting to {BASE_URL} ...")

    try:
        res = httpx.post(f"{BASE_URL}/api/fetch", timeout=30.0)
    except httpx.ConnectError:
        print("ERROR: Could not connect. Is the server running?")
        print("  Start it with: uvicorn main:app --reload")
        return 1

    if res.status_code == 429:
        print(f"RATE LIMITED: {res.json().get('detail', 'quota exceeded')}")
        print("Try again tomorrow after quota resets.")
        return 1

    if res.status_code >= 400:
        print(f"ERROR {res.status_code}: {res.json().get('detail', res.text)}")
        return 1

    data = res.json()
    print(f"OK — {data['updated']} bills updated, {data['new_actions']} new actions")

    if data.get("errors"):
        print(f"  {len(data['errors'])} bill(s) failed:")
        for err in data["errors"]:
            print(f"    {err['bill_id']}: {err['error']}")

    if data.get("skipped"):
        print(f"  Note: {data['skipped']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify the script handles a missing server gracefully**

```bash
cd /Users/raphaelchen/Desktop/ilga_tracker && source .venv/bin/activate && python scripts/check_api.py
```

Expected output (server not running):
```
Connecting to http://127.0.0.1:8000 ...
ERROR: Could not connect. Is the server running?
  Start it with: uvicorn main:app --reload
```
Expected exit code: 1 (run `echo $?` to confirm)

- [ ] **Step 3: Commit**

```bash
cd /Users/raphaelchen/Desktop/ilga_tracker && git add scripts/check_api.py && git commit -m "scripts: add manual API health check script"
```

---

## Task 4: Migration tests

**Files:**
- Create: `tests/test_migrate.py`

**Context:** `scripts/migrate.py` imports `get_connection` from `database` as `from database import get_connection`. To patch it in migration tests, use `patch("scripts.migrate.get_connection", ...)`. The existing `db` fixture already patches `database.get_connection` and `services.bills.get_connection` — migration tests extend this by adding `scripts.migrate.get_connection`.

- [ ] **Step 1: Create `tests/test_migrate.py`**

```python
import csv
import pytest
from pathlib import Path
from unittest.mock import patch
from scripts.migrate import parse_bill_id_from_url, seed_from_csv
from tests.conftest import FAKE_BILL


# ── parse_bill_id_from_url ────────────────────────────────────────────────────

def test_parse_hb_url():
    url = "https://www.ilga.gov/legislation/BillStatus.asp?DocTypeID=HB&DocNum=1288&GAID=17"
    assert parse_bill_id_from_url(url) == "HB1288"


def test_parse_sb_url():
    url = "https://www.ilga.gov/legislation/BillStatus.asp?DocTypeID=SB&DocNum=0086&GAID=17"
    assert parse_bill_id_from_url(url) == "SB0086"


def test_parse_missing_doc_type():
    url = "https://www.ilga.gov/legislation/BillStatus.asp?DocNum=1288"
    assert parse_bill_id_from_url(url) is None


def test_parse_missing_doc_num():
    url = "https://www.ilga.gov/legislation/BillStatus.asp?DocTypeID=HB"
    assert parse_bill_id_from_url(url) is None


def test_parse_empty_string():
    assert parse_bill_id_from_url("") is None


# ── seed_from_csv ─────────────────────────────────────────────────────────────

@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "test_updates.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["Bill", "Date", "Chamber", "Action", "Webpage Title"]
        )
        writer.writeheader()
        writer.writerow({"Bill": "HB1288", "Date": "1/15/2025", "Chamber": "House",
                         "Action": "First reading", "Webpage Title": "SOME BILL"})
        writer.writerow({"Bill": "HB1288", "Date": "1/20/2025", "Chamber": "House",
                         "Action": "Second reading", "Webpage Title": "SOME BILL"})
        writer.writerow({"Bill": "SB0019", "Date": "1/16/2025", "Chamber": "Senate",
                         "Action": "First reading", "Webpage Title": "OTHER BILL"})
    return path


def test_seed_from_csv_inserts_bills(db, csv_file):
    with patch("scripts.migrate.get_connection", return_value=db):
        seed_from_csv(csv_file)

    bills = db.execute("SELECT id FROM bills ORDER BY id").fetchall()
    assert len(bills) == 2
    assert bills[0]["id"] == "HB1288"
    assert bills[1]["id"] == "SB0019"


def test_seed_from_csv_inserts_actions(db, csv_file):
    with patch("scripts.migrate.get_connection", return_value=db):
        seed_from_csv(csv_file)

    actions = db.execute(
        "SELECT * FROM actions ORDER BY order_num"
    ).fetchall()
    assert len(actions) == 3
    assert actions[0]["bill_id"] == "HB1288"
    assert actions[0]["description"] == "First reading"
    assert actions[2]["bill_id"] == "SB0019"


def test_seed_from_csv_idempotent(db, csv_file):
    """Running seed_from_csv twice does not duplicate bills or actions."""
    with patch("scripts.migrate.get_connection", return_value=db):
        seed_from_csv(csv_file)
        seed_from_csv(csv_file)

    bill_count = db.execute("SELECT COUNT(*) FROM bills").fetchone()[0]
    action_count = db.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
    assert bill_count == 2
    assert action_count == 3
```

- [ ] **Step 2: Run the tests**

```bash
cd /Users/raphaelchen/Desktop/ilga_tracker && source .venv/bin/activate && pytest tests/test_migrate.py -v
```

Expected: 8 passed

- [ ] **Step 3: Commit**

```bash
cd /Users/raphaelchen/Desktop/ilga_tracker && git add tests/test_migrate.py && git commit -m "test: add migration URL parsing and CSV import tests"
```

---

## Task 5: Concurrent fetch test

**Files:**
- Create: `tests/test_concurrent.py`

**Context:** `asyncio.gather()` runs both coroutines concurrently in the same event loop. Since SQLite WAL mode allows multiple readers but serializes writes, the `INSERT OR IGNORE` on `UNIQUE(bill_id, order_num)` guarantees actions are not duplicated even if both fetches race to insert the same row.

- [ ] **Step 1: Create `tests/test_concurrent.py`**

```python
import asyncio
import pytest
from unittest.mock import patch, AsyncMock
from services.bills import fetch_all_updates
from tests.conftest import FAKE_BILL


async def test_concurrent_fetch_both_complete(db):
    """Two simultaneous fetch_all_updates() calls both return valid responses."""
    with db:
        db.execute(
            "INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test', '104th')"
        )

    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        results = await asyncio.gather(
            fetch_all_updates(),
            fetch_all_updates(),
        )

    assert len(results) == 2
    for result in results:
        assert "updated" in result
        assert "new_actions" in result
        assert "errors" in result
        assert result["errors"] == []


async def test_concurrent_fetch_no_duplicate_actions(db):
    """Two concurrent fetches do not duplicate actions — INSERT OR IGNORE handles the race."""
    with db:
        db.execute(
            "INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test', '104th')"
        )

    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        await asyncio.gather(
            fetch_all_updates(),
            fetch_all_updates(),
        )

    count = db.execute(
        "SELECT COUNT(*) FROM actions WHERE bill_id = 'HB1288'"
    ).fetchone()[0]
    assert count == 1
```

- [ ] **Step 2: Run the tests**

```bash
cd /Users/raphaelchen/Desktop/ilga_tracker && source .venv/bin/activate && pytest tests/test_concurrent.py -v
```

Expected: 2 passed

- [ ] **Step 3: Run the full suite to confirm nothing regressed**

```bash
cd /Users/raphaelchen/Desktop/ilga_tracker && source .venv/bin/activate && pytest tests/ -v
```

Expected: all tests pass (42 existing + 1 export + 2 persistence + 8 migrate + 2 concurrent = 55 total)

- [ ] **Step 4: Commit**

```bash
cd /Users/raphaelchen/Desktop/ilga_tracker && git add tests/test_concurrent.py && git commit -m "test: add concurrent fetch correctness test"
```
