# Supabase Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the SQLite database with Supabase (PostgreSQL) so data is cloud-hosted, accessible to multiple developers, and compatible with multi-instance Fly.io deployments.

**Architecture:** A module-level `asyncpg` connection pool is created in `database.py` at startup and stored globally. Service functions in `services/bills.py` acquire connections from the pool. The pool is initialized in `main.py`'s lifespan handler and closed on shutdown.

**Tech Stack:** `asyncpg` (PostgreSQL async driver), Supabase (managed Postgres), FastAPI lifespan events, `pytest-asyncio` for tests.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `requirements.txt` | Modify | Add `asyncpg` |
| `config.py` | Modify | Add `DATABASE_URL` env var |
| `database.py` | Rewrite | asyncpg pool lifecycle + Postgres DDL |
| `main.py` | Modify | Wire pool startup/shutdown into lifespan |
| `services/bills.py` | Rewrite | All queries async, Postgres SQL syntax |
| `routers/bills.py` | Modify | Make sync handlers `async def` |
| `routers/actions.py` | Modify | Make sync handlers `async def` |
| `scripts/migrate.py` | Modify | Update to use asyncpg pool |
| `scripts/sqlite_to_supabase.py` | Create | One-time data copy SQLite → Supabase |
| `fly.toml` | Modify | Remove `[[mounts]]` volume section |
| `tests/conftest.py` | Create | Shared asyncpg pool fixture |
| `tests/test_bills_service.py` | Create | Service layer tests |

---

## Task 1: Add asyncpg dependency and DATABASE_URL config

**Files:**
- Modify: `requirements.txt`
- Modify: `config.py`

- [ ] **Step 1: Add asyncpg to requirements.txt**

Open `requirements.txt` and add one line after `httpx`:

```
asyncpg>=0.29.0
```

- [ ] **Step 2: Add DATABASE_URL to config.py**

Replace the contents of `config.py` with:

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OPENSTATES_API_KEY: str = os.getenv("OPENSTATES_API_KEY", "")
OPENSTATES_BASE_URL: str = "https://v3.openstates.org"
IL_JURISDICTION: str = "ocd-jurisdiction/country:us/state:il/government"
IL_SESSION: str = "104th"

DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# Kept for one-time SQLite→Supabase migration script only
DB_PATH: Path = Path(__file__).parent / "data" / "tracker.db"

if not OPENSTATES_API_KEY:
    import warnings
    warnings.warn(
        "OPENSTATES_API_KEY is not set. Set it in a .env file to enable live fetching.",
        stacklevel=1,
    )

if not DATABASE_URL:
    import warnings
    warnings.warn(
        "DATABASE_URL is not set. Set it in a .env file to connect to Supabase.",
        stacklevel=1,
    )
```

- [ ] **Step 3: Add DATABASE_URL to .env**

Open `.env` and add:

```
DATABASE_URL="postgresql://postgres.<project-ref>:<password>@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
```

(Replace with your actual Supabase connection string — find it in Supabase dashboard → Project Settings → Database → Connection string → URI mode.)

- [ ] **Step 4: Install the new dependency**

```bash
pip install asyncpg>=0.29.0
```

Expected: asyncpg installs without errors.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt config.py
git commit -m "feat: add asyncpg dependency and DATABASE_URL config"
```

---

## Task 2: Rewrite database.py for asyncpg pool

**Files:**
- Rewrite: `database.py`
- Create: `tests/conftest.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write the failing test**

Create `tests/conftest.py`:

```python
import os
import pytest
import asyncpg
import pytest_asyncio

TEST_DATABASE_URL = os.getenv("DATABASE_URL", "")

@pytest_asyncio.fixture
async def pool():
    if not TEST_DATABASE_URL:
        pytest.skip("DATABASE_URL not set")
    p = await asyncpg.create_pool(TEST_DATABASE_URL)
    yield p
    await p.close()
```

Create `tests/test_database.py`:

```python
import pytest
import pytest_asyncio
from database import create_pool, close_pool, init_db, get_pool

@pytest.mark.asyncio
async def test_pool_creates_and_closes():
    await create_pool()
    pool = get_pool()
    assert pool is not None
    await close_pool()

@pytest.mark.asyncio
async def test_init_db_creates_tables():
    await create_pool()
    await init_db()
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name IN ('bills', 'actions')"
        )
    assert result == 2
    await close_pool()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_database.py -v
```

Expected: FAIL — `ImportError: cannot import name 'create_pool'` (database.py not yet updated).

- [ ] **Step 3: Rewrite database.py**

Replace all contents of `database.py`:

```python
import asyncpg
from config import DATABASE_URL

_pool: asyncpg.Pool | None = None


async def create_pool() -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    assert _pool is not None, "Database pool not initialized — call create_pool() first"
    return _pool


async def init_db() -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bills (
                id              TEXT PRIMARY KEY,
                title           TEXT,
                session         TEXT,
                added_at        TEXT DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS'),
                last_fetched_at TEXT,
                note            TEXT NOT NULL DEFAULT '',
                source_url      TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS actions (
                id          SERIAL PRIMARY KEY,
                bill_id     TEXT    NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
                date        TEXT,
                chamber     TEXT,
                description TEXT,
                order_num   INTEGER,
                UNIQUE(bill_id, order_num)
            );
        """)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_database.py -v
```

Expected: PASS — both tests pass.

- [ ] **Step 5: Commit**

```bash
git add database.py tests/conftest.py tests/test_database.py
git commit -m "feat: replace sqlite3 database layer with asyncpg pool"
```

---

## Task 3: Update main.py lifespan

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Update main.py to use async pool lifecycle**

Replace the lifespan function in `main.py`:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database import create_pool, close_pool, init_db
from routers import bills, actions, fetch, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_pool()
    await init_db()
    yield
    await close_pool()


app = FastAPI(title="Illinois Legislative Tracker", lifespan=lifespan)


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


app.include_router(auth.router)
app.include_router(bills.router)
app.include_router(actions.router)
app.include_router(fetch.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")
```

- [ ] **Step 2: Verify app starts without error**

```bash
uvicorn main:app --reload
```

Expected: Server starts, no import errors. (May warn about missing DATABASE_URL if .env not filled in yet — that's fine.)

Stop the server with Ctrl+C.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: wire asyncpg pool into FastAPI lifespan"
```

---

## Task 4: Rewrite services/bills.py for asyncpg

**Files:**
- Rewrite: `services/bills.py`
- Create: `tests/test_bills_service.py`

> **asyncpg API reference for this task:**
> - `conn.fetch(query, *args)` → `list[Record]` (use for SELECT many)
> - `conn.fetchrow(query, *args)` → `Record | None` (use for SELECT one)
> - `conn.execute(query, *args)` → `str` command tag (`"DELETE 1"`, `"UPDATE 1"`, `"INSERT 0 1"`)
> - Parameters use `$1, $2, ...` positional placeholders (not `?`)
> - `dict(record)` works to convert a Record to a plain dict

- [ ] **Step 1: Write failing tests**

Create `tests/test_bills_service.py`:

```python
import pytest
import pytest_asyncio
import asyncpg
import database

@pytest_asyncio.fixture(autouse=True)
async def setup_db(pool):
    database._pool = pool
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bills (
                id TEXT PRIMARY KEY, title TEXT, session TEXT,
                added_at TEXT DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS'),
                last_fetched_at TEXT, note TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS actions (
                id SERIAL PRIMARY KEY, bill_id TEXT NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
                date TEXT, chamber TEXT, description TEXT, order_num INTEGER,
                UNIQUE(bill_id, order_num)
            );
        """)
    yield
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS actions; DROP TABLE IF EXISTS bills;")
    database._pool = None

@pytest.mark.asyncio
async def test_get_all_bills_empty():
    from services.bills import get_all_bills
    result = await get_all_bills()
    assert result == []

@pytest.mark.asyncio
async def test_bill_exists_false():
    from services.bills import bill_exists
    assert await bill_exists("HB9999") is False

@pytest.mark.asyncio
async def test_remove_bill_not_found():
    from services.bills import remove_bill
    assert await remove_bill("HB9999") is False

@pytest.mark.asyncio
async def test_update_bill_note_not_found():
    from services.bills import update_bill_note
    assert await update_bill_note("HB9999", "test") is False

@pytest.mark.asyncio
async def test_get_actions_empty():
    from services.bills import get_actions
    result = await get_actions()
    assert result == []

@pytest.mark.asyncio
async def test_bill_crud(pool):
    from services.bills import get_all_bills, bill_exists, remove_bill, update_bill_note
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO bills (id, title, session) VALUES ($1, $2, $3)",
            "HB1288", "Test Bill", "104th"
        )
    assert await bill_exists("HB1288") is True
    bills = await get_all_bills()
    assert any(b["id"] == "HB1288" for b in bills)
    assert await update_bill_note("HB1288", "my note") is True
    assert await remove_bill("HB1288") is True
    assert await bill_exists("HB1288") is False

@pytest.mark.asyncio
async def test_get_actions_filtered(pool):
    from services.bills import get_actions
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO bills (id) VALUES ($1)", "HB1288")
        await conn.execute(
            "INSERT INTO actions (bill_id, date, chamber, description, order_num) VALUES ($1,$2,$3,$4,$5)",
            "HB1288", "2025-01-01", "house", "Introduced", 1
        )
    result = await get_actions("HB1288")
    assert len(result) == 1
    assert result[0]["description"] == "Introduced"
    assert await get_actions("HB9999") == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_bills_service.py -v
```

Expected: FAIL — service functions not yet updated (still sync/sqlite3).

- [ ] **Step 3: Rewrite services/bills.py**

Replace all contents of `services/bills.py`:

```python
from datetime import datetime, timezone, timedelta
from database import get_pool
from services.openstates import fetch_bills, extract_chamber, RateLimitError, DailyQuotaError

CACHE_HOURS = 12


async def get_all_bills() -> list[dict]:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, session, added_at, note, source_url FROM bills ORDER BY id"
        )
        return [dict(r) for r in rows]


async def bill_exists(bill_id: str) -> bool:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM bills WHERE id = $1", bill_id)
        return row is not None


async def remove_bill(bill_id: str) -> bool:
    async with get_pool().acquire() as conn:
        status = await conn.execute("DELETE FROM bills WHERE id = $1", bill_id)
        return status == "DELETE 1"


async def update_bill_note(bill_id: str, note: str) -> bool:
    async with get_pool().acquire() as conn:
        status = await conn.execute(
            "UPDATE bills SET note = $1 WHERE id = $2", note, bill_id
        )
        return status == "UPDATE 1"


async def get_actions(bill_id: str | None = None) -> list[dict]:
    async with get_pool().acquire() as conn:
        if bill_id:
            rows = await conn.fetch(
                "SELECT bill_id, date, chamber, description FROM actions "
                "WHERE bill_id = $1 ORDER BY order_num",
                bill_id,
            )
        else:
            rows = await conn.fetch(
                "SELECT bill_id, date, chamber, description FROM actions "
                "ORDER BY bill_id, order_num"
            )
        return [dict(r) for r in rows]


async def add_bill(bill_id: str) -> dict:
    results = await fetch_bills([bill_id])
    _, data = results[0]
    if isinstance(data, Exception):
        raise data

    title = data.get("title", "")
    session = data.get("session", "")
    sources = data.get("sources", [])
    source_url = sources[0].get("url", "") if sources else ""

    async with get_pool().acquire() as conn:
        await conn.execute(
            "INSERT INTO bills (id, title, session, source_url) VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (id) DO NOTHING",
            bill_id, title, session, source_url,
        )
        await _upsert_actions(conn, bill_id, data.get("actions", []))

    return {"id": bill_id, "title": title, "session": session}


async def fetch_all_updates() -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=CACHE_HOURS)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT id FROM bills WHERE last_fetched_at IS NULL OR last_fetched_at < $1",
            cutoff_str,
        )
        bill_ids = [r["id"] for r in rows]

    if not bill_ids:
        return {
            "updated": 0, "new_actions": 0, "errors": [],
            "skipped": "all bills fetched within the last 12 hours",
        }

    results = await fetch_bills(bill_ids)

    quota_hits = [r for r in results if isinstance(r[1], DailyQuotaError)]
    if quota_hits:
        fetched = len(results) - len(quota_hits)
        raise DailyQuotaError(
            f"{str(quota_hits[0][1])} ({fetched} of {len(bill_ids)} bills fetched before quota was hit)"
        )

    rate_limited = [r for r in results if isinstance(r[1], RateLimitError)]
    if len(rate_limited) == len(results):
        raise RateLimitError(str(rate_limited[0][1]))

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    new_actions = 0
    errors = []

    async with get_pool().acquire() as conn:
        for bill_id, data in results:
            if isinstance(data, Exception):
                errors.append({"bill_id": bill_id, "error": str(data)})
                continue
            sources = data.get("sources", [])
            source_url = sources[0].get("url", "") if sources else ""
            await conn.execute(
                "UPDATE bills SET title = $1, session = $2, last_fetched_at = $3, source_url = $4 "
                "WHERE id = $5",
                data.get("title", ""), data.get("session", ""), now_str, source_url, bill_id,
            )
            new_actions += await _upsert_actions(conn, bill_id, data.get("actions", []))

    return {"updated": len(bill_ids) - len(errors), "new_actions": new_actions, "errors": errors}


async def _upsert_actions(conn, bill_id: str, actions: list[dict]) -> int:
    inserted = 0
    for action in actions:
        status = await conn.execute(
            "INSERT INTO actions (bill_id, date, chamber, description, order_num) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (bill_id, order_num) DO NOTHING",
            bill_id,
            action.get("date", ""),
            extract_chamber(action),
            action.get("description", ""),
            action.get("order", 0),
        )
        if status == "INSERT 0 1":
            inserted += 1
    return inserted
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_bills_service.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/bills.py tests/test_bills_service.py
git commit -m "feat: rewrite bills service for asyncpg"
```

---

## Task 5: Update routers to use async service functions

**Files:**
- Modify: `routers/bills.py`
- Modify: `routers/actions.py`

The service functions are now all `async`, so router handlers that call them must also be `async def`.

- [ ] **Step 1: Update routers/bills.py**

Replace all contents of `routers/bills.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services.bills import get_all_bills, bill_exists, remove_bill, add_bill, update_bill_note
from services.openstates import normalize_bill_id
from routers.auth import require_admin

router = APIRouter(prefix="/api/bills", tags=["bills"])


class AddBillRequest(BaseModel):
    bill_id: str


class UpdateNoteRequest(BaseModel):
    note: str


@router.get("")
async def list_bills() -> list[dict]:
    return await get_all_bills()


@router.post("", status_code=201, dependencies=[Depends(require_admin)])
async def create_bill(body: AddBillRequest) -> dict:
    bill_id = normalize_bill_id(body.bill_id)
    if await bill_exists(bill_id):
        raise HTTPException(status_code=409, detail=f"{bill_id} is already tracked")
    try:
        return await add_bill(bill_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{bill_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_bill(bill_id: str) -> None:
    if not await remove_bill(normalize_bill_id(bill_id)):
        raise HTTPException(status_code=404, detail=f"{bill_id} not found")


@router.put("/{bill_id}/note", dependencies=[Depends(require_admin)])
async def update_note(bill_id: str, body: UpdateNoteRequest) -> dict:
    normalized = normalize_bill_id(bill_id)
    if not await update_bill_note(normalized, body.note):
        raise HTTPException(status_code=404, detail=f"{bill_id} not found")
    return {"bill_id": normalized, "note": body.note}
```

- [ ] **Step 2: Update routers/actions.py**

Replace all contents of `routers/actions.py`:

```python
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from services.bills import get_actions
from services.openstates import normalize_bill_id

router = APIRouter(prefix="/api/actions", tags=["actions"])


@router.get("")
async def list_actions(bill_id: str | None = Query(default=None)) -> list[dict]:
    if bill_id:
        bill_id = normalize_bill_id(bill_id)
    return await get_actions(bill_id)


@router.get("/export")
async def export_actions() -> JSONResponse:
    """Download all cached actions as a JSON file."""
    return JSONResponse(
        content=await get_actions(),
        headers={
            "Content-Disposition": "attachment; filename=legislative_tracker_updates.json"
        },
    )
```

- [ ] **Step 3: Verify the app still starts**

```bash
uvicorn main:app --reload
```

Expected: Server starts cleanly. Visit `http://localhost:8000/api/bills` — should return `[]` or your bill list from Supabase.

Stop with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add routers/bills.py routers/actions.py
git commit -m "feat: make router handlers async to match asyncpg service layer"
```

---

## Task 6: Update scripts/migrate.py for asyncpg

**Files:**
- Modify: `scripts/migrate.py`

- [ ] **Step 1: Rewrite scripts/migrate.py**

Replace all contents of `scripts/migrate.py`:

```python
"""
One-time migration: parse Legislative Tracker Bills.txt and seed the database.

Usage (from the ilga_tracker/ directory):

    # Full migration — fetches bill metadata from OpenStates (requires API key)
    python -m scripts.migrate

    # Import existing CSV only, skip OpenStates fetch (no API key needed)
    python -m scripts.migrate --skip-api --csv legislative_tracker_updates.csv

    # Custom file paths
    python -m scripts.migrate --bills-file path/to/bills.txt --csv path/to/updates.csv
"""

import sys
import csv
import re
import asyncio
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import create_pool, close_pool, init_db, get_pool
from services.openstates import normalize_bill_id, fetch_bills, extract_chamber


def parse_bill_id_from_url(url: str) -> str | None:
    doc_type = re.search(r"DocTypeID=([A-Za-z]+)", url)
    doc_num = re.search(r"DocNum=(\d+)", url)
    if doc_type and doc_num:
        return f"{doc_type.group(1).upper()}{doc_num.group(1)}"
    return None


async def seed_from_openstates(bill_ids: list[str]) -> None:
    print(f"\nFetching {len(bill_ids)} bills from OpenStates...")
    results = await fetch_bills(bill_ids)

    async with get_pool().acquire() as conn:
        for bill_id, data in results:
            if isinstance(data, Exception):
                print(f"  SKIP {bill_id}: {data}")
                continue
            await conn.execute(
                "INSERT INTO bills (id, title, session) VALUES ($1, $2, $3) "
                "ON CONFLICT (id) DO NOTHING",
                bill_id, data.get("title", ""), data.get("session", ""),
            )
            inserted = await _insert_actions(conn, bill_id, data.get("actions", []))
            print(f"  OK   {bill_id}: {data.get('title', '')[:60]}  ({inserted} actions)")


async def seed_from_csv(csv_path: Path) -> None:
    print(f"\nImporting actions from {csv_path}...")
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    async with get_pool().acquire() as conn:
        bills_seen: set[str] = set()
        for order_num, row in enumerate(rows):
            bill_id = normalize_bill_id(row["Bill"])
            if bill_id not in bills_seen:
                await conn.execute(
                    "INSERT INTO bills (id, title, session) VALUES ($1, $2, $3) "
                    "ON CONFLICT (id) DO NOTHING",
                    bill_id, row.get("Webpage Title", ""), "2025-2026",
                )
                bills_seen.add(bill_id)
            await conn.execute(
                "INSERT INTO actions (bill_id, date, chamber, description, order_num) "
                "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (bill_id, order_num) DO NOTHING",
                bill_id, row["Date"], row["Chamber"], row["Action"], order_num,
            )
    print(f"  Imported {len(rows)} rows for {len(bills_seen)} bills.")


async def _insert_actions(conn, bill_id: str, actions: list[dict]) -> int:
    inserted = 0
    for action in actions:
        status = await conn.execute(
            "INSERT INTO actions (bill_id, date, chamber, description, order_num) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (bill_id, order_num) DO NOTHING",
            bill_id,
            action.get("date", ""),
            extract_chamber(action),
            action.get("description", ""),
            action.get("order", 0),
        )
        if status == "INSERT 0 1":
            inserted += 1
    return inserted


async def run(args) -> None:
    await create_pool()
    await init_db()

    bills_path = Path(args.bills_file)
    if not bills_path.exists():
        print(f"Error: bills file not found: {bills_path}")
        sys.exit(1)

    with open(bills_path, encoding="utf-8-sig") as f:
        lines = [l.strip() for l in f if l.strip()]

    bill_ids: list[str] = []
    for line in lines:
        if line.startswith("http"):
            bid = parse_bill_id_from_url(line)
            if bid:
                bill_ids.append(bid)
            else:
                print(f"  Could not parse URL: {line}")
        else:
            bill_ids.append(normalize_bill_id(line))

    print(f"Parsed {len(bill_ids)} bill IDs: {bill_ids}")

    if args.csv:
        await seed_from_csv(Path(args.csv))

    if not args.skip_api:
        await seed_from_openstates(bill_ids)

    await close_pool()
    print("\nMigration complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the tracker database from existing files.")
    parser.add_argument("--bills-file", default="Legislative Tracker Bills.txt")
    parser.add_argument("--csv", default=None)
    parser.add_argument("--skip-api", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add scripts/migrate.py
git commit -m "feat: update migrate script to use asyncpg"
```

---

## Task 7: Write one-time SQLite → Supabase migration script

**Files:**
- Create: `scripts/sqlite_to_supabase.py`

This script copies all existing data from your local `data/tracker.db` into Supabase. Run it once, then you're done.

- [ ] **Step 1: Create scripts/sqlite_to_supabase.py**

```python
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

    pg_conn = await asyncpg.connect(DATABASE_URL)

    bills = sqlite_conn.execute("SELECT * FROM bills").fetchall()
    print(f"Migrating {len(bills)} bills...")
    for bill in bills:
        await pg_conn.execute(
            "INSERT INTO bills (id, title, session, added_at, last_fetched_at, note, source_url) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (id) DO NOTHING",
            bill["id"], bill["title"], bill["session"], bill["added_at"],
            bill["last_fetched_at"], bill["note"], bill["source_url"],
        )

    actions = sqlite_conn.execute("SELECT * FROM actions").fetchall()
    print(f"Migrating {len(actions)} actions...")
    for action in actions:
        await pg_conn.execute(
            "INSERT INTO actions (bill_id, date, chamber, description, order_num) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (bill_id, order_num) DO NOTHING",
            action["bill_id"], action["date"], action["chamber"],
            action["description"], action["order_num"],
        )

    sqlite_conn.close()
    await pg_conn.close()
    print(f"Done. Migrated {len(bills)} bills and {len(actions)} actions.")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run it against your local database**

Make sure `.env` has your `DATABASE_URL` set and `data/tracker.db` exists, then:

```bash
python -m scripts.sqlite_to_supabase
```

Expected output:
```
Migrating N bills...
Migrating M actions...
Done. Migrated N bills and M actions.
```

Verify in Supabase dashboard → Table Editor that bills and actions appear.

- [ ] **Step 3: Commit**

```bash
git add scripts/sqlite_to_supabase.py
git commit -m "feat: add one-time SQLite to Supabase migration script"
```

---

## Task 8: Deploy to Fly.io

**Files:**
- Modify: `fly.toml`

- [ ] **Step 1: Set DATABASE_URL as a Fly.io secret**

```bash
fly secrets set DATABASE_URL="postgresql://postgres.<project-ref>:<password>@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
```

Use the same connection string you put in `.env`.

Expected: `Secrets are staged for the first deployment`

- [ ] **Step 2: Remove the volume mount from fly.toml**

Open `fly.toml` and delete the `[[mounts]]` section entirely:

```toml
# DELETE these three lines:
[[mounts]]
  source = 'tracker_data'
  destination = '/app/data'
```

The file should no longer contain any `[[mounts]]` block.

- [ ] **Step 3: Deploy**

```bash
fly deploy
```

Expected: Build and deploy succeed. Check logs:

```bash
fly logs
```

Expected: No errors. The app starts, pool connects to Supabase, tables already exist (no-op `CREATE TABLE IF NOT EXISTS`).

- [ ] **Step 4: Smoke test the live app**

```bash
curl https://ilga-tracker.fly.dev/api/bills
```

Expected: Returns your bill list as JSON (same data you migrated from SQLite).

- [ ] **Step 5: Commit fly.toml**

```bash
git add fly.toml
git commit -m "chore: remove Fly.io volume mount — database now on Supabase"
```

---

## Post-Migration Cleanup (optional, after verifying everything works)

- Delete `data/tracker.db` from your local machine (data is now in Supabase)
- Remove `DB_PATH` from `config.py` (no longer needed once `sqlite_to_supabase.py` has been run)
- Delete `scripts/sqlite_to_supabase.py` (one-time script, no longer needed)
- Detach the Fly.io volume: `fly volumes list` then `fly volumes destroy <id>`
