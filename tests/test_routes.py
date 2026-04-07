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


# ── GET /api/actions/export ───────────────────────────────────────────────────

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
