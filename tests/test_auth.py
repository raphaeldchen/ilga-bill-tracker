import os
import pytest
import sqlite3
from fastapi.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def auth_client(monkeypatch):
    """TestClient with in-memory DB and ADMIN_PASSWORD set."""
    monkeypatch.setenv("ADMIN_PASSWORD", "testpass")

    from database import init_db
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    with patch("database.get_connection", return_value=conn), \
         patch("services.bills.get_connection", return_value=conn):
        init_db()
        from main import app
        with TestClient(app) as c:
            yield c

    conn.close()


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
