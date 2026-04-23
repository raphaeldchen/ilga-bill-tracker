import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from routers.auth import COOKIE_NAME


@pytest.fixture
def auth_client(monkeypatch):
    """TestClient with mocked asyncpg pool and ADMIN_PASSWORD set."""
    monkeypatch.setenv("ADMIN_PASSWORD", "testpass")

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


def test_write_api_without_cookie_returns_401(auth_client):
    res = auth_client.post("/api/bills", json={"bill_id": "HB1288"})
    assert res.status_code == 401


def test_delete_api_without_cookie_returns_401(auth_client):
    res = auth_client.delete("/api/bills/HB1288")
    assert res.status_code == 401


def test_fetch_api_without_cookie_returns_401(auth_client):
    res = auth_client.post("/api/fetch")
    assert res.status_code == 401


def test_read_apis_accessible_without_cookie(auth_client):
    res = auth_client.get("/api/bills")
    assert res.status_code == 200
    res = auth_client.get("/api/actions")
    assert res.status_code == 200


def test_login_page_accessible(auth_client):
    res = auth_client.get("/login")
    assert res.status_code == 200


def test_login_success_redirects_to_admin(auth_client):
    res = auth_client.post(
        "/login",
        data={"password": "testpass"},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert res.headers["location"] == "/admin"
    assert COOKIE_NAME in res.cookies


def test_login_wrong_password_redirects_back_with_error(auth_client):
    res = auth_client.post(
        "/login",
        data={"password": "wrong"},
        follow_redirects=False,
    )
    assert res.status_code == 303
    assert "login" in res.headers["location"]
    assert "error" in res.headers["location"]
    assert COOKIE_NAME not in res.cookies


def test_admin_page_without_cookie_redirects_to_login(auth_client):
    res = auth_client.get("/admin", follow_redirects=False)
    assert res.status_code == 303
    assert "/login" in res.headers["location"]


def test_admin_page_with_valid_cookie(auth_client):
    auth_client.post("/login", data={"password": "testpass"})
    res = auth_client.get("/admin")
    assert res.status_code == 200


def test_logout_redirects_to_root(auth_client):
    auth_client.post("/login", data={"password": "testpass"})
    res = auth_client.get("/logout", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/"
