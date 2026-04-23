import asyncio
import pytest
import pytest_asyncio
import database
from unittest.mock import patch, AsyncMock
from services.bills import fetch_all_updates
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
async def test_concurrent_fetch_both_complete(pool):
    """Two simultaneous fetch_all_updates() calls both return valid responses."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO bills (id, title, session) VALUES ($1, $2, $3)",
            "HB1288", "Test", "104th",
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


@pytest.mark.asyncio
async def test_concurrent_fetch_no_duplicate_actions(pool):
    """Two concurrent fetches do not duplicate actions — ON CONFLICT DO NOTHING handles the race."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO bills (id, title, session) VALUES ($1, $2, $3)",
            "HB1288", "Test", "104th",
        )

    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        await asyncio.gather(
            fetch_all_updates(),
            fetch_all_updates(),
        )

    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM actions WHERE bill_id = $1", "HB1288"
        )
    assert count == 1
