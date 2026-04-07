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


# ── fetch_all_updates ─────────────────────────────────────────────────────────

from datetime import datetime, timezone, timedelta
from services.bills import fetch_all_updates
from services.openstates import RateLimitError


async def test_fetch_empty_db_returns_zeros(db):
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        result = await fetch_all_updates()

    mock_fetch.assert_not_called()
    assert result["updated"] == 0
    assert result["new_actions"] == 0
    assert result["errors"] == []


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
