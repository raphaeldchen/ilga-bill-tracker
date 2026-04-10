# Pre-Deploy Checks Design

**Date:** 2026-04-07
**Scope:** Additional automated tests and a manual API check script to verify system correctness before first deployment.

---

## Overview

Five additions to the project in priority order:

1. Export endpoint test — add to `tests/test_routes.py`
2. DB persistence test — new `tests/test_persistence.py`
3. Real API check script — new `scripts/check_api.py`
4. Migration tests — new `tests/test_migrate.py`
5. Concurrent fetch test — new `tests/test_concurrent.py`

---

## 1. Export Endpoint Test (add to `tests/test_routes.py`)

**What:** `GET /api/actions/export` returns all cached actions as a downloadable JSON file.

**Test:** Insert two bills with one action each using the `client` + `db` fixtures. Call the endpoint. Assert:
- HTTP 200
- `Content-Disposition: attachment; filename=legislative_tracker_updates.json` header present
- Response body is valid JSON containing both actions

---

## 2. DB Persistence (`tests/test_persistence.py`)

**What:** Data written to `tracker.db` survives closing and reopening a connection — i.e. the DB is a real file, not in-memory.

**Approach:** Uses pytest's `tmp_path` fixture to create a temp `.db` file. Patches only `database.DB_PATH` to point at the temp file — `get_connection()` is intentionally **not** mocked so the test uses real file-based connections. The test:
1. Calls `init_db()` to create schema in the temp file
2. Inserts a bill via a real file-based connection (through `get_connection()`)
3. Opens a **second, independent connection** directly to the same temp file
4. Reads the bill back and asserts it is present

**Why a real file:** The in-memory fixtures used in other tests prove logic but cannot catch misconfiguration of `DB_PATH` or any code that accidentally opens a second `:memory:` connection (which would be empty).

---

## 3. Real API Check Script (`scripts/check_api.py`)

**What:** A standalone script run manually after daily quota resets to verify the full OpenStates integration works end-to-end.

**Behavior:**
- Requires the server to be running at `http://127.0.0.1:8000`
- POSTs to `/api/fetch`
- Prints a human-readable summary: bills updated, new actions, any per-bill errors
- Exits with code 0 on success (even if 0 new actions — that's valid)
- Exits with code 1 on HTTP error (429 rate limit, 503 service error, connection refused)

**Usage:**
```bash
source .venv/bin/activate && python scripts/check_api.py
```

---

## 4. Migration Tests (`tests/test_migrate.py`)

**What:** Tests the `scripts/migrate.py` subsystem — URL parsing and CSV import.

### `parse_bill_id_from_url` (pure function, no DB needed)
- Valid HB URL with `DocTypeID=HB&DocNum=1288` → `"HB1288"`
- Valid SB URL → `"SB0086"`
- URL missing `DocTypeID` → `None`
- URL missing `DocNum` → `None`
- Empty string → `None`

### `seed_from_csv` (uses in-memory DB + tmp CSV file)
- Write a 3-row CSV to a temp file with columns: `Bill`, `Date`, `Chamber`, `Action`, `Webpage Title`
- Patch `get_connection` to use an in-memory DB (same pattern as existing tests)
- Call `seed_from_csv(path)`
- Assert: correct number of bills inserted, correct number of actions inserted

---

## 5. Concurrent Fetch Test (`tests/test_concurrent.py`)

**What:** Two simultaneous `fetch_all_updates()` calls via `asyncio.gather()` with mocked `fetch_bills`.

**Setup:** Insert one bill in the in-memory DB. Mock `fetch_bills` to return a valid bill with one action.

**Assertions:**
- Both calls complete without exception
- Both return valid response dicts with `updated`, `new_actions`, `errors` keys
- Total action count in DB is 1 (not 2) — `INSERT OR IGNORE` on `UNIQUE(bill_id, order_num)` deduplicates

---

## Files Changed

| Action | Path |
|--------|------|
| Modify | `tests/test_routes.py` |
| Create | `tests/test_persistence.py` |
| Create | `tests/test_migrate.py` |
| Create | `tests/test_concurrent.py` |
| Create | `scripts/check_api.py` |
