import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from tests.conftest import FAKE_BILL
from routers.auth import _make_cookie_value, COOKIE_NAME


@pytest.fixture
def client(monkeypatch):
    import database

    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock(return_value="DELETE 0")

    mock_acquire_ctx = MagicMock()
    mock_acquire_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_acquire_ctx)
    database._pool = mock_pool

    with patch("main.create_pool", AsyncMock(return_value=mock_pool)), \
         patch("main.init_db", AsyncMock()), \
         patch("main.close_pool", AsyncMock()):
        from main import app
        with TestClient(app) as c:
            yield c

    database._pool = None


@pytest.fixture
def auth_client(client):
    """client with a valid signed admin session cookie pre-set."""
    client.cookies.set(COOKIE_NAME, _make_cookie_value())
    return client


# ── GET /api/bills ────────────────────────────────────────────────────────────

def test_list_bills_empty(client):
    with patch("routers.bills.get_all_bills", new_callable=AsyncMock, return_value=[]):
        res = client.get("/api/bills")
    assert res.status_code == 200
    assert res.json() == []


def test_list_bills(client):
    bills = [{"id": "HB1288", "title": "Test Bill", "session": "104th",
              "added_at": "2025-01-01 00:00:00", "note": "", "source_url": ""}]
    with patch("routers.bills.get_all_bills", new_callable=AsyncMock, return_value=bills):
        res = client.get("/api/bills")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == "HB1288"
    assert data[0]["title"] == "Test Bill"


# ── POST /api/bills ───────────────────────────────────────────────────────────

def test_add_bill_route_success(auth_client):
    with patch("routers.bills.bill_exists", new_callable=AsyncMock, return_value=False), \
         patch("routers.bills.add_bill", new_callable=AsyncMock,
               return_value={"id": "HB1288", "title": "TEST BILL", "session": "104th"}):
        res = auth_client.post("/api/bills", json={"bill_id": "HB1288"})
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "HB1288"
    assert data["title"] == "TEST BILL"


def test_add_bill_normalizes_input(auth_client):
    with patch("routers.bills.bill_exists", new_callable=AsyncMock, return_value=False), \
         patch("routers.bills.add_bill", new_callable=AsyncMock,
               return_value={"id": "HB1288", "title": "TEST BILL", "session": "104th"}):
        res = auth_client.post("/api/bills", json={"bill_id": "hb 1288"})
    assert res.status_code == 201
    assert res.json()["id"] == "HB1288"


def test_add_bill_duplicate_returns_409(auth_client):
    with patch("routers.bills.bill_exists", new_callable=AsyncMock, return_value=True):
        res = auth_client.post("/api/bills", json={"bill_id": "HB1288"})
    assert res.status_code == 409
    assert "already tracked" in res.json()["detail"]


def test_add_bill_not_found_returns_404(auth_client):
    with patch("routers.bills.bill_exists", new_callable=AsyncMock, return_value=False), \
         patch("routers.bills.add_bill", new_callable=AsyncMock,
               side_effect=ValueError("No results found for HB9999 in session 104th")):
        res = auth_client.post("/api/bills", json={"bill_id": "HB9999"})
    assert res.status_code == 404
    assert "No results found" in res.json()["detail"]


# ── DELETE /api/bills/{bill_id} ───────────────────────────────────────────────

def test_delete_bill(auth_client):
    with patch("routers.bills.remove_bill", new_callable=AsyncMock, return_value=True):
        res = auth_client.delete("/api/bills/HB1288")
    assert res.status_code == 204


def test_delete_bill_not_found_returns_404(auth_client):
    with patch("routers.bills.remove_bill", new_callable=AsyncMock, return_value=False):
        res = auth_client.delete("/api/bills/HB9999")
    assert res.status_code == 404


# ── GET /api/actions ──────────────────────────────────────────────────────────

def test_get_actions_empty(client):
    with patch("routers.actions.get_actions", new_callable=AsyncMock, return_value=[]):
        res = client.get("/api/actions")
    assert res.status_code == 200
    assert res.json() == []


def test_get_actions_returns_all(client):
    actions = [
        {"bill_id": "HB1288", "date": "2025-01-15", "chamber": "House", "description": "First reading"},
        {"bill_id": "SB0019", "date": "2025-01-16", "chamber": "Senate", "description": "First reading"},
    ]
    with patch("routers.actions.get_actions", new_callable=AsyncMock, return_value=actions):
        res = client.get("/api/actions")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_get_actions_filter_by_bill(client):
    actions = [
        {"bill_id": "HB1288", "date": "2025-01-15", "chamber": "House", "description": "First reading"},
    ]
    with patch("routers.actions.get_actions", new_callable=AsyncMock, return_value=actions):
        res = client.get("/api/actions?bill_id=HB1288")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["bill_id"] == "HB1288"


# ── POST /api/fetch ───────────────────────────────────────────────────────────

def test_fetch_updates_success(auth_client):
    with patch("services.bills.fetch_bills", new_callable=AsyncMock,
               return_value=[("HB1288", FAKE_BILL)]), \
         patch("services.bills.get_pool") as mock_get_pool:
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[MagicMock(__getitem__=lambda s, k: "HB1288")])
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        mock_acquire_ctx = MagicMock()
        mock_acquire_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_acquire_ctx)
        mock_get_pool.return_value = mock_pool
        res = auth_client.post("/api/fetch")
    assert res.status_code == 200


def test_fetch_updates_rate_limit_returns_429(auth_client):
    from services.openstates import RateLimitError
    with patch("services.bills.fetch_bills", new_callable=AsyncMock,
               return_value=[("HB1288", RateLimitError("rate limit exceeded"))]), \
         patch("services.bills.get_pool") as mock_get_pool:
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[MagicMock(__getitem__=lambda s, k: "HB1288")])
        mock_acquire_ctx = MagicMock()
        mock_acquire_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_acquire_ctx)
        mock_get_pool.return_value = mock_pool
        res = auth_client.post("/api/fetch")
    assert res.status_code == 429


# ── GET /api/actions/export ───────────────────────────────────────────────────

def test_export_actions(client):
    actions = [
        {"bill_id": "HB1288", "date": "2025-01-15", "chamber": "House", "description": "First reading"},
        {"bill_id": "SB0019", "date": "2025-01-16", "chamber": "Senate", "description": "First reading"},
    ]
    with patch("routers.actions.get_actions", new_callable=AsyncMock, return_value=actions):
        res = client.get("/api/actions/export")
    assert res.status_code == 200
    assert "attachment" in res.headers["content-disposition"]
    assert "legislative_tracker_updates.json" in res.headers["content-disposition"]
    data = res.json()
    assert len(data) == 2
    bill_ids = {a["bill_id"] for a in data}
    assert bill_ids == {"HB1288", "SB0019"}


# ── PUT /api/bills/{bill_id}/note ─────────────────────────────────────────────

def test_update_note_success(auth_client):
    with patch("routers.bills.update_bill_note", new_callable=AsyncMock, return_value=True):
        res = auth_client.put("/api/bills/HB1288/note", json={"note": "Important bill"})
    assert res.status_code == 200
    assert res.json() == {"bill_id": "HB1288", "note": "Important bill"}


def test_update_note_clears_note(auth_client):
    with patch("routers.bills.update_bill_note", new_callable=AsyncMock, return_value=True):
        res = auth_client.put("/api/bills/HB1288/note", json={"note": ""})
    assert res.status_code == 200
    assert res.json()["note"] == ""


def test_update_note_not_found_returns_404(auth_client):
    with patch("routers.bills.update_bill_note", new_callable=AsyncMock, return_value=False):
        res = auth_client.put("/api/bills/HB9999/note", json={"note": "test"})
    assert res.status_code == 404


def test_update_note_requires_auth(client):
    res = client.put("/api/bills/HB1288/note", json={"note": "test"})
    assert res.status_code == 401


def test_list_bills_includes_note_field(client):
    bills = [{"id": "HB1288", "title": "Test Bill", "session": "104th",
              "added_at": "2025-01-01 00:00:00", "note": "", "source_url": ""}]
    with patch("routers.bills.get_all_bills", new_callable=AsyncMock, return_value=bills):
        res = client.get("/api/bills")
    assert res.status_code == 200
    assert "note" in res.json()[0]
    assert res.json()[0]["note"] == ""
