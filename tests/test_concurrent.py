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
