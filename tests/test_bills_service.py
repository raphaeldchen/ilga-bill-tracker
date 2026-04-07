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
