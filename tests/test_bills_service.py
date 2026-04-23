import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
import database
from tests.conftest import FAKE_BILL


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


@pytest.mark.asyncio
async def test_add_bill_success(pool):
    from services.bills import add_bill
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        result = await add_bill("HB1288")

    assert result["id"] == "HB1288"
    assert result["title"] == "TEST BILL"
    assert result["session"] == "104th"

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM bills WHERE id = $1", "HB1288")
        actions = await conn.fetch("SELECT * FROM actions WHERE bill_id = $1", "HB1288")
    assert row is not None
    assert row["title"] == "TEST BILL"
    assert len(actions) == 1
    assert actions[0]["description"] == "First reading"


@pytest.mark.asyncio
async def test_add_bill_not_found_raises(pool):
    from services.bills import add_bill
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB9999", ValueError("No results found for HB9999 in session 104th"))]
        with pytest.raises(ValueError, match="No results found"):
            await add_bill("HB9999")

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM bills WHERE id = $1", "HB9999")
    assert row is None


@pytest.mark.asyncio
async def test_fetch_empty_db_returns_zeros():
    from services.bills import fetch_all_updates
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        result = await fetch_all_updates()
    mock_fetch.assert_not_called()
    assert result["updated"] == 0
    assert result["new_actions"] == 0
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_fetch_null_last_fetched_is_fetched(pool):
    from services.bills import fetch_all_updates
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO bills (id, title, session) VALUES ($1, $2, $3)",
            "HB1288", "Test", "104th"
        )
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        result = await fetch_all_updates()
    mock_fetch.assert_called_once_with(["HB1288"])
    assert result["updated"] == 1
    assert result["new_actions"] == 1
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_fetch_skips_recent_bills(pool):
    from services.bills import fetch_all_updates
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO bills (id, title, session, last_fetched_at) VALUES ($1,$2,$3,$4)",
            "HB1288", "Test", "104th", now,
        )
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        result = await fetch_all_updates()
    mock_fetch.assert_not_called()
    assert "skipped" in result


@pytest.mark.asyncio
async def test_fetch_stale_bills_are_fetched(pool):
    from services.bills import fetch_all_updates
    stale = (datetime.now(timezone.utc) - timedelta(hours=13)).strftime("%Y-%m-%d %H:%M:%S")
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO bills (id, title, session, last_fetched_at) VALUES ($1,$2,$3,$4)",
            "HB1288", "Test", "104th", stale,
        )
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        result = await fetch_all_updates()
    mock_fetch.assert_called_once_with(["HB1288"])
    assert result["updated"] == 1


@pytest.mark.asyncio
async def test_fetch_upsert_ignores_duplicate_actions(pool):
    from services.bills import fetch_all_updates
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO bills (id, title, session) VALUES ($1,$2,$3)",
            "HB1288", "Test", "104th"
        )
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        await fetch_all_updates()

    stale = (datetime.now(timezone.utc) - timedelta(hours=13)).strftime("%Y-%m-%d %H:%M:%S")
    async with pool.acquire() as conn:
        await conn.execute("UPDATE bills SET last_fetched_at = $1 WHERE id = $2", stale, "HB1288")

    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        result = await fetch_all_updates()

    assert result["new_actions"] == 0
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM actions WHERE bill_id = $1", "HB1288")
    assert count == 1


@pytest.mark.asyncio
async def test_fetch_partial_errors(pool):
    from services.bills import fetch_all_updates
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO bills (id, title, session) VALUES ($1,$2,$3)", "HB1288", "Test", "104th")
        await conn.execute("INSERT INTO bills (id, title, session) VALUES ($1,$2,$3)", "SB9999", "Test", "104th")

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


@pytest.mark.asyncio
async def test_list_bills_includes_note(pool):
    from services.bills import get_all_bills
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO bills (id, title, session, note) VALUES ($1,$2,$3,$4)",
            "HB1288", "Test", "104th", "My note"
        )
    bills = await get_all_bills()
    assert bills[0]["note"] == "My note"


@pytest.mark.asyncio
async def test_list_bills_note_defaults_empty(pool):
    from services.bills import get_all_bills
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO bills (id, title, session) VALUES ($1,$2,$3)",
            "HB1288", "Test", "104th"
        )
    bills = await get_all_bills()
    assert bills[0]["note"] == ""
