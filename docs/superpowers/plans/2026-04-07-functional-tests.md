# Functional Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pytest functional test suite covering utility functions, service logic (including caching), and all HTTP routes — with no real network calls and no file-based SQLite.

**Architecture:** In-memory SQLite per test (via a `db` fixture that patches `services.bills.get_connection`). OpenStates API calls are intercepted by patching `services.bills.fetch_bills` with `AsyncMock` per test. FastAPI routes are exercised through `TestClient` from `starlette.testclient`.

**Tech Stack:** Python, pytest, pytest-asyncio, unittest.mock (stdlib), FastAPI TestClient

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `requirements.txt` | Add pytest, pytest-asyncio |
| Create | `pytest.ini` | Set asyncio_mode=auto |
| Create | `tests/__init__.py` | Make tests a package |
| Create | `tests/conftest.py` | Shared fixtures: db, client |
| Create | `tests/test_utils.py` | normalize_bill_id, to_openstates_identifier, extract_chamber |
| Create | `tests/test_bills_service.py` | add_bill, get_actions, fetch_all_updates |
| Create | `tests/test_routes.py` | All HTTP endpoints |

---

## Task 1: Setup — dependencies, pytest.ini, conftest.py

**Files:**
- Modify: `requirements.txt`
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Add test dependencies to requirements.txt**

Append to `requirements.txt`:
```
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 2: Create pytest.ini**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 3: Install new dependencies**

Run:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: pytest and pytest-asyncio install without errors.

- [ ] **Step 4: Create tests/__init__.py (empty)**

```python
```

- [ ] **Step 5: Create tests/conftest.py**

```python
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
```

- [ ] **Step 6: Verify test discovery**

Run:
```bash
pytest tests/ --collect-only
```

Expected: `no tests ran` with 0 errors (no test files yet, but discovery works).

- [ ] **Step 7: Commit**

```bash
git add requirements.txt pytest.ini tests/__init__.py tests/conftest.py
git commit -m "test: add pytest setup, conftest with in-memory DB fixture"
```

---

## Task 2: Utility function tests

**Files:**
- Create: `tests/test_utils.py`

- [ ] **Step 1: Create tests/test_utils.py**

```python
import pytest
from services.openstates import normalize_bill_id, to_openstates_identifier, extract_chamber


# ── normalize_bill_id ─────────────────────────────────────────────────────────

def test_normalize_lowercase():
    assert normalize_bill_id("hb1288") == "HB1288"

def test_normalize_with_space():
    assert normalize_bill_id("HB 1288") == "HB1288"

def test_normalize_lowercase_with_space():
    assert normalize_bill_id("hb 1288") == "HB1288"

def test_normalize_mixed_case():
    assert normalize_bill_id("sB0086") == "SB0086"

def test_normalize_leading_trailing_whitespace():
    assert normalize_bill_id("  HB1288  ") == "HB1288"

def test_normalize_already_normalized():
    assert normalize_bill_id("HB1288") == "HB1288"


# ── to_openstates_identifier ──────────────────────────────────────────────────

def test_to_openstates_hb():
    assert to_openstates_identifier("HB1288") == "HB 1288"

def test_to_openstates_sb():
    assert to_openstates_identifier("SB0086") == "SB 0086"

def test_to_openstates_no_match_passes_through():
    # Non-standard IDs are returned unchanged
    assert to_openstates_identifier("UNKNOWN") == "UNKNOWN"


# ── extract_chamber ───────────────────────────────────────────────────────────

def test_extract_chamber_lower():
    action = {"organization": {"classification": "lower", "name": "House"}}
    assert extract_chamber(action) == "House"

def test_extract_chamber_upper():
    action = {"organization": {"classification": "upper", "name": "Senate"}}
    assert extract_chamber(action) == "Senate"

def test_extract_chamber_fallback_by_name_house():
    action = {"organization": {"classification": "", "name": "Illinois House"}}
    assert extract_chamber(action) == "House"

def test_extract_chamber_fallback_by_name_senate():
    action = {"organization": {"classification": "", "name": "Illinois Senate"}}
    assert extract_chamber(action) == "Senate"

def test_extract_chamber_unknown():
    action = {"organization": {"classification": "joint", "name": "Joint Committee"}}
    assert extract_chamber(action) == "joint"

def test_extract_chamber_missing_org():
    assert extract_chamber({}) == "Unknown"
```

- [ ] **Step 2: Run utility tests**

Run:
```bash
pytest tests/test_utils.py -v
```

Expected: all 15 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_utils.py
git commit -m "test: add utility function tests for normalize, identifier, chamber"
```

---

## Task 3: Service tests — add_bill and get_actions

**Files:**
- Create: `tests/test_bills_service.py`

- [ ] **Step 1: Create tests/test_bills_service.py with add_bill tests**

```python
import pytest
from unittest.mock import patch, AsyncMock
from services.bills import add_bill, get_actions
from tests.conftest import FAKE_BILL


# ── add_bill ──────────────────────────────────────────────────────────────────

async def test_add_bill_success(db):
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        result = await add_bill("HB1288")

    assert result["id"] == "HB1288"
    assert result["title"] == "TEST BILL"
    assert result["session"] == "104th"

    # Bill row was inserted
    row = db.execute("SELECT * FROM bills WHERE id = 'HB1288'").fetchone()
    assert row is not None
    assert row["title"] == "TEST BILL"

    # Actions were inserted
    actions = db.execute("SELECT * FROM actions WHERE bill_id = 'HB1288'").fetchall()
    assert len(actions) == 1
    assert actions[0]["description"] == "First reading"
    assert actions[0]["chamber"] == "House"


async def test_add_bill_not_found_raises(db):
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB9999", ValueError("No results found for HB9999 in session 104th"))]
        with pytest.raises(ValueError, match="No results found"):
            await add_bill("HB9999")

    # Nothing was inserted
    row = db.execute("SELECT * FROM bills WHERE id = 'HB9999'").fetchone()
    assert row is None


async def test_add_bill_duplicate_is_ignored(db):
    """INSERT OR IGNORE means calling add_bill twice doesn't raise or duplicate."""
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        await add_bill("HB1288")
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        await add_bill("HB1288")

    count = db.execute("SELECT COUNT(*) FROM bills WHERE id = 'HB1288'").fetchone()[0]
    assert count == 1

    action_count = db.execute("SELECT COUNT(*) FROM actions WHERE bill_id = 'HB1288'").fetchone()[0]
    assert action_count == 1  # UNIQUE constraint prevents duplicates


# ── get_actions ───────────────────────────────────────────────────────────────

def test_get_actions_empty(db):
    assert get_actions() == []


def test_get_actions_returns_all(db):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Bill A', '104th')")
        db.execute("INSERT INTO bills (id, title, session) VALUES ('SB0019', 'Bill B', '104th')")
        db.execute("INSERT INTO actions (bill_id, date, chamber, description, order_num) VALUES ('HB1288', '2025-01-15', 'House', 'First reading', 1)")
        db.execute("INSERT INTO actions (bill_id, date, chamber, description, order_num) VALUES ('SB0019', '2025-01-16', 'Senate', 'First reading', 1)")

    actions = get_actions()
    assert len(actions) == 2
    bill_ids = {a["bill_id"] for a in actions}
    assert bill_ids == {"HB1288", "SB0019"}


def test_get_actions_filtered_by_bill(db):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Bill A', '104th')")
        db.execute("INSERT INTO bills (id, title, session) VALUES ('SB0019', 'Bill B', '104th')")
        db.execute("INSERT INTO actions (bill_id, date, chamber, description, order_num) VALUES ('HB1288', '2025-01-15', 'House', 'First reading', 1)")
        db.execute("INSERT INTO actions (bill_id, date, chamber, description, order_num) VALUES ('SB0019', '2025-01-16', 'Senate', 'First reading', 1)")

    actions = get_actions("HB1288")
    assert len(actions) == 1
    assert actions[0]["bill_id"] == "HB1288"
```

- [ ] **Step 2: Run add_bill and get_actions tests**

Run:
```bash
pytest tests/test_bills_service.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_bills_service.py
git commit -m "test: add add_bill and get_actions service tests"
```

---

## Task 4: Service tests — fetch_all_updates

**Files:**
- Modify: `tests/test_bills_service.py`

- [ ] **Step 1: Append fetch_all_updates tests to tests/test_bills_service.py**

Add this block at the end of the file:

```python
from datetime import datetime, timezone, timedelta
from services.bills import fetch_all_updates
from services.openstates import RateLimitError


# ── fetch_all_updates ─────────────────────────────────────────────────────────

async def test_fetch_empty_db_returns_zeros(db):
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        result = await fetch_all_updates()

    mock_fetch.assert_not_called()
    assert result == {"updated": 0, "new_actions": 0, "errors": []}


async def test_fetch_null_last_fetched_is_fetched(db):
    """Bills with last_fetched_at IS NULL are always fetched."""
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test', '104th')")

    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        result = await fetch_all_updates()

    mock_fetch.assert_called_once_with(["HB1288"])
    assert result["updated"] == 1
    assert result["new_actions"] == 1
    assert result["errors"] == []


async def test_fetch_skips_recent_bills(db):
    """Bills fetched within the last 12 hours are skipped entirely."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with db:
        db.execute(
            "INSERT INTO bills (id, title, session, last_fetched_at) VALUES ('HB1288', 'Test', '104th', ?)",
            (now,),
        )

    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        result = await fetch_all_updates()

    mock_fetch.assert_not_called()
    assert result["updated"] == 0
    assert result["new_actions"] == 0


async def test_fetch_stale_bills_are_fetched(db):
    """Bills with last_fetched_at older than 12 hours are fetched."""
    stale = (datetime.now(timezone.utc) - timedelta(hours=13)).strftime("%Y-%m-%d %H:%M:%S")
    with db:
        db.execute(
            "INSERT INTO bills (id, title, session, last_fetched_at) VALUES ('HB1288', 'Test', '104th', ?)",
            (stale,),
        )

    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        result = await fetch_all_updates()

    mock_fetch.assert_called_once_with(["HB1288"])
    assert result["updated"] == 1


async def test_fetch_stamps_last_fetched_at(db):
    """Successful fetch updates last_fetched_at on the bill row."""
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test', '104th')")

    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        await fetch_all_updates()

    row = db.execute("SELECT last_fetched_at FROM bills WHERE id = 'HB1288'").fetchone()
    assert row["last_fetched_at"] is not None


async def test_fetch_upsert_ignores_duplicate_actions(db):
    """Running fetch twice does not duplicate actions."""
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test', '104th')")

    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        await fetch_all_updates()

    # Make bill stale so it gets fetched again
    stale = (datetime.now(timezone.utc) - timedelta(hours=13)).strftime("%Y-%m-%d %H:%M:%S")
    with db:
        db.execute("UPDATE bills SET last_fetched_at = ? WHERE id = 'HB1288'", (stale,))

    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        result = await fetch_all_updates()

    assert result["new_actions"] == 0  # already existed, INSERT OR IGNORE skipped them
    count = db.execute("SELECT COUNT(*) FROM actions WHERE bill_id = 'HB1288'").fetchone()[0]
    assert count == 1


async def test_fetch_partial_errors(db):
    """Failed bills appear in errors; successful bills still update."""
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test', '104th')")
        db.execute("INSERT INTO bills (id, title, session) VALUES ('SB9999', 'Test', '104th')")

    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [
            ("HB1288", FAKE_BILL),
            ("SB9999", ValueError("No results found for SB9999")),
        ]
        result = await fetch_all_updates()

    assert result["updated"] == 1
    assert result["new_actions"] == 1
    assert len(result["errors"]) == 1
    assert result["errors"][0]["bill_id"] == "SB9999"


async def test_fetch_all_cached_returns_skipped_message(db):
    """When all bills are fresh, returns skipped message without calling API."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with db:
        db.execute(
            "INSERT INTO bills (id, title, session, last_fetched_at) VALUES ('HB1288', 'Test', '104th', ?)",
            (now,),
        )

    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        result = await fetch_all_updates()

    mock_fetch.assert_not_called()
    assert "skipped" in result
```

- [ ] **Step 2: Run all service tests**

Run:
```bash
pytest tests/test_bills_service.py -v
```

Expected: all 15 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_bills_service.py
git commit -m "test: add fetch_all_updates service tests including caching behavior"
```

---

## Task 5: Route tests

**Files:**
- Create: `tests/test_routes.py`

- [ ] **Step 1: Create tests/test_routes.py**

```python
import pytest
from unittest.mock import patch, AsyncMock
from tests.conftest import FAKE_BILL


# ── GET /api/bills ────────────────────────────────────────────────────────────

def test_list_bills_empty(client):
    res = client.get("/api/bills")
    assert res.status_code == 200
    assert res.json() == []


def test_list_bills(client, db):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test Bill', '104th')")

    res = client.get("/api/bills")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == "HB1288"
    assert data[0]["title"] == "Test Bill"


# ── POST /api/bills ───────────────────────────────────────────────────────────

def test_add_bill_route_success(client):
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        res = client.post("/api/bills", json={"bill_id": "HB1288"})

    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "HB1288"
    assert data["title"] == "TEST BILL"


def test_add_bill_normalizes_input(client):
    """Lowercase and spaced input is normalized before lookup."""
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        res = client.post("/api/bills", json={"bill_id": "hb 1288"})

    assert res.status_code == 201
    assert res.json()["id"] == "HB1288"


def test_add_bill_duplicate_returns_409(client, db):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test Bill', '104th')")

    res = client.post("/api/bills", json={"bill_id": "HB1288"})
    assert res.status_code == 409
    assert "already tracked" in res.json()["detail"]


def test_add_bill_not_found_returns_404(client):
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB9999", ValueError("No results found for HB9999 in session 104th"))]
        res = client.post("/api/bills", json={"bill_id": "HB9999"})

    assert res.status_code == 404
    assert "No results found" in res.json()["detail"]


# ── DELETE /api/bills/{bill_id} ───────────────────────────────────────────────

def test_delete_bill(client, db):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test Bill', '104th')")
        db.execute("INSERT INTO actions (bill_id, date, chamber, description, order_num) VALUES ('HB1288', '2025-01-15', 'House', 'First reading', 1)")

    res = client.delete("/api/bills/HB1288")
    assert res.status_code == 204

    # Bill and its actions are gone
    row = db.execute("SELECT * FROM bills WHERE id = 'HB1288'").fetchone()
    assert row is None
    actions = db.execute("SELECT * FROM actions WHERE bill_id = 'HB1288'").fetchall()
    assert len(actions) == 0


def test_delete_bill_not_found_returns_404(client):
    res = client.delete("/api/bills/HB9999")
    assert res.status_code == 404


# ── GET /api/actions ──────────────────────────────────────────────────────────

def test_get_actions_empty(client):
    res = client.get("/api/actions")
    assert res.status_code == 200
    assert res.json() == []


def test_get_actions_returns_all(client, db):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Bill A', '104th')")
        db.execute("INSERT INTO bills (id, title, session) VALUES ('SB0019', 'Bill B', '104th')")
        db.execute("INSERT INTO actions (bill_id, date, chamber, description, order_num) VALUES ('HB1288', '2025-01-15', 'House', 'First reading', 1)")
        db.execute("INSERT INTO actions (bill_id, date, chamber, description, order_num) VALUES ('SB0019', '2025-01-16', 'Senate', 'First reading', 1)")

    res = client.get("/api/actions")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_get_actions_filter_by_bill(client, db):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Bill A', '104th')")
        db.execute("INSERT INTO bills (id, title, session) VALUES ('SB0019', 'Bill B', '104th')")
        db.execute("INSERT INTO actions (bill_id, date, chamber, description, order_num) VALUES ('HB1288', '2025-01-15', 'House', 'First reading', 1)")
        db.execute("INSERT INTO actions (bill_id, date, chamber, description, order_num) VALUES ('SB0019', '2025-01-16', 'Senate', 'First reading', 1)")

    res = client.get("/api/actions?bill_id=HB1288")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["bill_id"] == "HB1288"


# ── POST /api/fetch ───────────────────────────────────────────────────────────

def test_fetch_updates_success(client, db):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test', '104th')")

    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        res = client.post("/api/fetch")

    assert res.status_code == 200
    data = res.json()
    assert data["updated"] == 1
    assert data["new_actions"] == 1
    assert data["errors"] == []


def test_fetch_updates_rate_limit_returns_429(client, db):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test', '104th')")

    from services.openstates import RateLimitError
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", RateLimitError("rate limit exceeded"))]
        res = client.post("/api/fetch")

    assert res.status_code == 429
```

- [ ] **Step 2: Run all route tests**

Run:
```bash
pytest tests/test_routes.py -v
```

Expected: all 15 tests pass.

- [ ] **Step 3: Run the full suite to confirm nothing regressed**

Run:
```bash
pytest tests/ -v
```

Expected: all 37 tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_routes.py
git commit -m "test: add HTTP route tests for all API endpoints"
```
