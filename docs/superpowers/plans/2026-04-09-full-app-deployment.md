# Full App Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the Illinois Legislative Tracker as a public web app on Fly.io with a read-only public view and a password-protected admin panel for write operations.

**Architecture:** FastAPI serves two HTML pages — a public read-only view at `/` and a password-protected admin panel at `/admin`. A signed session cookie (itsdangerous) gates write API routes and the admin page. Fly.io hosts the app with a 1GB persistent volume for SQLite.

**Tech Stack:** FastAPI, itsdangerous (URLSafeTimedSerializer), vanilla JS, SQLite on Fly.io persistent volume, Docker.

---

## File Map

**Create:**
- `routers/auth.py` — `/login`, `/logout`, `/admin` routes + `require_admin` dependency
- `static/login.html` — password form
- `static/admin.html` — full admin interface (add/remove bills, fetch updates, logout)
- `static/admin.js` — JS for admin page (all write actions + 401-to-redirect handling)
- `tests/test_auth.py` — auth route and dependency tests
- `Dockerfile` — container image
- `.dockerignore` — exclude .venv, data/, .env from image
- `fly.toml` — Fly.io app config with volume mount

**Modify:**
- `requirements.txt` — add `itsdangerous>=2.1.0` explicitly
- `main.py` — include `auth` router
- `routers/bills.py` — add `Depends(require_admin)` to POST and DELETE
- `routers/fetch.py` — add `Depends(require_admin)` to POST
- `static/index.html` — remove write controls (add form, remove buttons, fetch button)
- `static/app.js` — remove write functions, update `renderBills` to omit remove buttons

**Note on innerHTML safety:** All JS in this plan that builds HTML via template literals uses `escapeHtml()` on every value sourced from the database or API. Bill IDs are normalized server-side, but client-side escaping is applied everywhere as a defense-in-depth measure.

---

## Task 1: Add `itsdangerous` to requirements and create auth module

**Files:**
- Modify: `requirements.txt`
- Create: `routers/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Add `itsdangerous` to `requirements.txt`**

Add the line after `python-dotenv`:

```
itsdangerous>=2.1.0
```

Full `requirements.txt` after change:
```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
httpx>=0.27.0
python-dotenv>=1.0.0
itsdangerous>=2.1.0
aiofiles>=23.0.0
jinja2>=3.1.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
anyio>=4.0.0
```

- [ ] **Step 2: Install the new dependency**

```bash
pip install itsdangerous
```

Expected: installs successfully (likely already present as a transitive dep, so it just pins it).

- [ ] **Step 3: Write failing tests for `require_admin`**

Create `tests/test_auth.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they fail correctly**

```bash
pytest tests/test_auth.py -v
```

Expected: 3 FAIL (`require_admin` not yet imported/wired), 1 PASS (`test_read_apis_accessible_without_cookie`).

- [ ] **Step 5: Create `routers/auth.py`**

```python
import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import APIRouter, Cookie, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
COOKIE_NAME = "admin_session"
COOKIE_MAX_AGE = 8 * 60 * 60  # 8 hours

_serializer = URLSafeTimedSerializer(SECRET_KEY)


def _make_cookie_value() -> str:
    return _serializer.dumps("admin")


def require_admin(session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> None:
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        _serializer.loads(session, max_age=COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Session expired or invalid")


@router.get("/login")
def login_page():
    return FileResponse("static/login.html")


@router.post("/login")
async def login(request: Request):
    form = await request.form()
    password = form.get("password", "")
    admin_password = os.getenv("ADMIN_PASSWORD", "")

    if not admin_password or password != admin_password:
        return RedirectResponse(url="/login?error=1", status_code=303)

    resp = RedirectResponse(url="/admin", status_code=303)
    resp.set_cookie(
        COOKIE_NAME,
        _make_cookie_value(),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


@router.get("/admin")
def admin_page(session: str | None = Cookie(default=None, alias=COOKIE_NAME)):
    if not session:
        return RedirectResponse(url="/login", status_code=303)
    try:
        _serializer.loads(session, max_age=COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return RedirectResponse(url="/login", status_code=303)
    return FileResponse("static/admin.html")
```

- [ ] **Step 6: Run auth tests — expect 3 still failing (router not wired yet)**

```bash
pytest tests/test_auth.py::test_write_api_without_cookie_returns_401 -v
```

Expected: FAIL — `require_admin` not yet added to bill routes. This confirms the test targets the right behavior.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt routers/auth.py tests/test_auth.py
git commit -m "feat: add auth module with require_admin dependency and session cookie helpers"
```

---

## Task 2: Wire auth router into the app and protect write endpoints

**Files:**
- Modify: `main.py`
- Modify: `routers/bills.py`
- Modify: `routers/fetch.py`
- Modify: `tests/test_routes.py`

- [ ] **Step 1: Include auth router in `main.py`**

Full updated `main.py`:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database import init_db
from routers import bills, actions, fetch, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Illinois Legislative Tracker", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(bills.router)
app.include_router(actions.router)
app.include_router(fetch.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")
```

- [ ] **Step 2: Update `routers/bills.py` to add `require_admin` to write routes**

Full updated file:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services.bills import get_all_bills, bill_exists, remove_bill, add_bill
from services.openstates import normalize_bill_id
from routers.auth import require_admin

router = APIRouter(prefix="/api/bills", tags=["bills"])


class AddBillRequest(BaseModel):
    bill_id: str


@router.get("")
def list_bills() -> list[dict]:
    return get_all_bills()


@router.post("", status_code=201, dependencies=[Depends(require_admin)])
async def create_bill(body: AddBillRequest) -> dict:
    bill_id = normalize_bill_id(body.bill_id)
    if bill_exists(bill_id):
        raise HTTPException(status_code=409, detail=f"{bill_id} is already tracked")
    try:
        return await add_bill(bill_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{bill_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_bill(bill_id: str) -> None:
    if not remove_bill(normalize_bill_id(bill_id)):
        raise HTTPException(status_code=404, detail=f"{bill_id} not found")
```

- [ ] **Step 3: Update `routers/fetch.py` to add `require_admin`**

Full updated file:

```python
from fastapi import APIRouter, Depends, HTTPException
from services.bills import fetch_all_updates
from services.openstates import RateLimitError
from routers.auth import require_admin

router = APIRouter(prefix="/api", tags=["fetch"])


@router.post("/fetch", dependencies=[Depends(require_admin)])
async def trigger_fetch() -> dict:
    """
    Pull the latest actions for all tracked bills from OpenStates.
    Fires all requests concurrently. Returns a summary of what changed.
    """
    try:
        return await fetch_all_updates()
    except RateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
```

- [ ] **Step 4: Run auth tests — all 4 should now pass**

```bash
pytest tests/test_auth.py -v
```

Expected: all 4 PASS.

- [ ] **Step 5: Run full test suite to find newly broken write-route tests**

```bash
pytest -v
```

Expected: write route tests in `test_routes.py` now fail with 401 (`test_add_bill_route_success`, `test_add_bill_normalizes_input`, `test_add_bill_duplicate_returns_409`, `test_add_bill_not_found_returns_404`, `test_delete_bill`, `test_delete_bill_not_found_returns_404`, `test_fetch_updates_success`, `test_fetch_updates_rate_limit_returns_429`).

- [ ] **Step 6: Fix `tests/test_routes.py` — add auth cookie to write requests**

Add this import at the top of `tests/test_routes.py` (after existing imports):

```python
from routers.auth import _make_cookie_value, COOKIE_NAME
```

Add this fixture after the existing `client` fixture:

```python
@pytest.fixture
def auth_headers():
    """Returns a cookies dict with a valid signed admin session cookie."""
    return {COOKIE_NAME: _make_cookie_value()}
```

Update every write-route test to accept `auth_headers` and pass `cookies=auth_headers`:

```python
def test_add_bill_route_success(client, auth_headers):
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        res = client.post("/api/bills", json={"bill_id": "HB1288"}, cookies=auth_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "HB1288"
    assert data["title"] == "TEST BILL"


def test_add_bill_normalizes_input(client, auth_headers):
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        res = client.post("/api/bills", json={"bill_id": "hb 1288"}, cookies=auth_headers)
    assert res.status_code == 201
    assert res.json()["id"] == "HB1288"


def test_add_bill_duplicate_returns_409(client, db, auth_headers):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test Bill', '104th')")
    res = client.post("/api/bills", json={"bill_id": "HB1288"}, cookies=auth_headers)
    assert res.status_code == 409
    assert "already tracked" in res.json()["detail"]


def test_add_bill_not_found_returns_404(client, auth_headers):
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB9999", ValueError("No results found for HB9999 in session 104th"))]
        res = client.post("/api/bills", json={"bill_id": "HB9999"}, cookies=auth_headers)
    assert res.status_code == 404
    assert "No results found" in res.json()["detail"]


def test_delete_bill(client, db, auth_headers):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test Bill', '104th')")
        db.execute("INSERT INTO actions (bill_id, date, chamber, description, order_num) VALUES ('HB1288', '2025-01-15', 'House', 'First reading', 1)")
    res = client.delete("/api/bills/HB1288", cookies=auth_headers)
    assert res.status_code == 204
    row = db.execute("SELECT * FROM bills WHERE id = 'HB1288'").fetchone()
    assert row is None
    actions = db.execute("SELECT * FROM actions WHERE bill_id = 'HB1288'").fetchall()
    assert len(actions) == 0


def test_delete_bill_not_found_returns_404(client, auth_headers):
    res = client.delete("/api/bills/HB9999", cookies=auth_headers)
    assert res.status_code == 404


def test_fetch_updates_success(client, db, auth_headers):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test', '104th')")
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", FAKE_BILL)]
        res = client.post("/api/fetch", cookies=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["updated"] == 1
    assert data["new_actions"] == 1
    assert data["errors"] == []


def test_fetch_updates_rate_limit_returns_429(client, db, auth_headers):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test', '104th')")
    from services.openstates import RateLimitError
    with patch("services.bills.fetch_bills", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [("HB1288", RateLimitError("rate limit exceeded"))]
        res = client.post("/api/fetch", cookies=auth_headers)
    assert res.status_code == 429
```

- [ ] **Step 7: Run full test suite — all tests should pass**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 8: Add login/logout/admin route tests to `tests/test_auth.py`**

Add this import at the top of `tests/test_auth.py`:

```python
from routers.auth import COOKIE_NAME
```

Append these tests to `tests/test_auth.py`:

```python
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
```

- [ ] **Step 9: Run auth tests**

```bash
pytest tests/test_auth.py -v
```

Expected: all 10 tests PASS. (The `/admin` page test serves `static/admin.html` — create a placeholder file `static/admin.html` containing just `<html></html>` if the test fails due to missing file, then replace it in Task 4.)

- [ ] **Step 10: Commit**

```bash
git add main.py routers/bills.py routers/fetch.py tests/test_routes.py tests/test_auth.py
git commit -m "feat: protect write API routes with require_admin; update tests"
```

---

## Task 3: Update public `index.html` and `app.js` to read-only

**Files:**
- Modify: `static/index.html`
- Modify: `static/app.js`

- [ ] **Step 1: Rewrite `static/index.html`**

Replace the entire file:

```html
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Illinois Legislative Tracker</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css" />
  <link rel="stylesheet" href="/static/style.css" />
</head>
<body>

  <header class="app-header">
    <div class="header-inner">
      <div class="header-title">
        <strong>Illinois Legislative Tracker</strong>
      </div>
    </div>
  </header>

  <div id="toast" class="toast hidden"></div>

  <div class="app-body">

    <aside class="sidebar">
      <h6>Tracked Bills</h6>
      <ul id="bill-list" class="bill-list"></ul>
    </aside>

    <main class="main-content">
      <div class="table-toolbar">
        <span id="action-count" class="action-count"></span>
        <select id="bill-filter" onchange="applyFilter()">
          <option value="">All Bills</option>
        </select>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Bill</th>
              <th>Date</th>
              <th>Chamber</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="actions-tbody">
            <tr><td colspan="4" class="empty-state">Loading...</td></tr>
          </tbody>
        </table>
      </div>
    </main>

  </div>

  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Rewrite `static/app.js` — read-only version**

Replace the entire file. All dynamic values inserted into the DOM use `escapeHtml()`:

```javascript
let allActions = [];

document.addEventListener('DOMContentLoaded', () => {
  loadBills();
  loadActions();
});

async function loadBills() {
  const bills = await apiFetch('/api/bills');
  if (bills === null) return;
  renderBills(bills);
}

async function loadActions() {
  const actions = await apiFetch('/api/actions');
  if (actions === null) return;
  allActions = actions.sort((a, b) => parseDate(b.date) - parseDate(a.date));
  renderActions();
}

function renderBills(bills) {
  const list = document.getElementById('bill-list');
  if (bills.length === 0) {
    list.innerHTML = '<li style="color:var(--pico-muted-color);font-size:0.8rem">No bills tracked yet.</li>';
    document.getElementById('bill-filter').innerHTML = '<option value="">All Bills</option>';
    return;
  }

  // All values from DB are escaped before being inserted into the DOM.
  list.innerHTML = bills.map(b =>
    '<li><span>' + escapeHtml(b.id) + '</span></li>'
  ).join('');

  const filter = document.getElementById('bill-filter');
  const current = filter.value;
  filter.innerHTML = '<option value="">All Bills</option>' +
    bills.map(b =>
      '<option value="' + escapeHtml(b.id) + '">' + escapeHtml(b.id) + '</option>'
    ).join('');
  if (current) filter.value = current;
}

function renderActions() {
  const filterId = document.getElementById('bill-filter').value;
  const rows = filterId ? allActions.filter(a => a.bill_id === filterId) : allActions;

  document.getElementById('action-count').textContent =
    rows.length + ' action' + (rows.length !== 1 ? 's' : '');

  const tbody = document.getElementById('actions-tbody');
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No actions found.</td></tr>';
    return;
  }

  // All API values are passed through escapeHtml before DOM insertion.
  tbody.innerHTML = rows.map(a =>
    '<tr>' +
    '<td>' + escapeHtml(a.bill_id) + '</td>' +
    '<td>' + escapeHtml(a.date) + '</td>' +
    '<td>' + escapeHtml(a.chamber) + '</td>' +
    '<td>' + escapeHtml(a.description) + '</td>' +
    '</tr>'
  ).join('');
}

function applyFilter() {
  renderActions();
}

async function apiFetch(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(res.status + ' ' + res.statusText);
    return res.json();
  } catch (e) {
    showToast('Failed to load data: ' + e.message, 'error');
    return null;
  }
}

let toastTimer;
function showToast(message, type) {
  type = type || 'success';
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = 'toast ' + type;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function() { toast.classList.add('hidden'); }, 4000);
}

function parseDate(str) {
  if (!str) return 0;
  return new Date(str).getTime() || 0;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
```

- [ ] **Step 3: Verify the app loads**

Start the dev server:
```bash
uvicorn main:app --reload
```

Open `http://localhost:8000`. Verify:
- Bill list shows (read-only, no remove buttons, no add form)
- Actions table populates
- No "Fetch Updates" button in the header

- [ ] **Step 4: Commit**

```bash
git add static/index.html static/app.js
git commit -m "feat: make public index page read-only; escape all DOM-inserted values"
```

---

## Task 4: Create `static/login.html`

**Files:**
- Create: `static/login.html`

- [ ] **Step 1: Create `static/login.html`**

```html
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Admin Login - Illinois Legislative Tracker</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css" />
  <style>
    body {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
    }
    .login-card {
      width: 100%;
      max-width: 360px;
      padding: 2rem;
    }
    .login-card h2 { margin-bottom: 0.25rem; }
    .login-card p.subtitle {
      color: var(--pico-muted-color);
      font-size: 0.875rem;
      margin-bottom: 1.5rem;
    }
    .error-msg {
      color: var(--pico-del-color);
      font-size: 0.85rem;
      margin-bottom: 1rem;
      display: none;
    }
  </style>
</head>
<body>
  <div class="login-card">
    <h2>Admin Login</h2>
    <p class="subtitle">Illinois Legislative Tracker</p>

    <p class="error-msg" id="error-msg">Incorrect password. Please try again.</p>

    <form method="POST" action="/login">
      <label for="password">Password</label>
      <input
        type="password"
        id="password"
        name="password"
        placeholder="Enter admin password"
        autocomplete="current-password"
        required
      />
      <button type="submit">Sign in</button>
    </form>

    <p style="margin-top:1rem;font-size:0.8rem;">
      <a href="/">Back to public view</a>
    </p>
  </div>

  <script>
    if (new URLSearchParams(window.location.search).get('error')) {
      document.getElementById('error-msg').style.display = 'block';
    }
  </script>
</body>
</html>
```

- [ ] **Step 2: Verify login page**

Open `http://localhost:8000/login`. Verify:
- Centered password form
- Submit with wrong password shows "Incorrect password" error (URL becomes `/login?error=1`)
- Submit with correct password (set `ADMIN_PASSWORD=testpass` in `.env`) redirects to `/admin`

- [ ] **Step 3: Commit**

```bash
git add static/login.html
git commit -m "feat: add admin login page with error feedback"
```

---

## Task 5: Create `static/admin.html` and `static/admin.js`

**Files:**
- Create: `static/admin.html`
- Create: `static/admin.js`
- Modify: `static/style.css`

- [ ] **Step 1: Create `static/admin.html`**

```html
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Admin - Illinois Legislative Tracker</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css" />
  <link rel="stylesheet" href="/static/style.css" />
</head>
<body>

  <header class="app-header">
    <div class="header-inner">
      <div class="header-title">
        <strong>Illinois Legislative Tracker</strong>
        <span class="admin-badge">Admin</span>
        <span id="last-updated" class="last-updated"></span>
      </div>
      <div class="header-actions">
        <button id="fetch-btn" onclick="fetchUpdates()">Fetch Updates</button>
        <a href="/logout" role="button" class="secondary outline logout-btn">Log out</a>
      </div>
    </div>
  </header>

  <div id="toast" class="toast hidden"></div>

  <div class="app-body">

    <aside class="sidebar">
      <h6>Tracked Bills</h6>
      <ul id="bill-list" class="bill-list"></ul>

      <div class="add-bill-form">
        <input
          id="add-bill-input"
          type="text"
          placeholder="e.g. HB1288"
          onkeydown="if(event.key==='Enter') addBill()"
        />
        <button id="add-bill-btn" onclick="addBill()" class="add-btn">Add</button>
      </div>
      <p id="add-error" class="add-error hidden"></p>
    </aside>

    <main class="main-content">
      <div class="table-toolbar">
        <span id="action-count" class="action-count"></span>
        <select id="bill-filter" onchange="applyFilter()">
          <option value="">All Bills</option>
        </select>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Bill</th>
              <th>Date</th>
              <th>Chamber</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="actions-tbody">
            <tr><td colspan="4" class="empty-state">Loading...</td></tr>
          </tbody>
        </table>
      </div>
    </main>

  </div>

  <script src="/static/admin.js"></script>
</body>
</html>
```

- [ ] **Step 2: Append admin styles to `static/style.css`**

Append to the end of `static/style.css`:

```css
/* ── Admin badge ────────────────────────────────────────────── */

.admin-badge {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  background: var(--pico-primary);
  color: #fff;
  padding: 0.15rem 0.45rem;
  border-radius: var(--pico-border-radius);
  vertical-align: middle;
}

.logout-btn {
  margin: 0;
  padding: 0.4rem 0.9rem;
  font-size: 0.85rem;
}
```

- [ ] **Step 3: Create `static/admin.js`**

All dynamic values are passed through `escapeHtml()` before DOM insertion. The `apiFetch` wrapper redirects to `/login` on 401 so an expired session is handled gracefully:

```javascript
let allActions = [];

document.addEventListener('DOMContentLoaded', function() {
  loadBills();
  loadActions();
});

async function loadBills() {
  const bills = await apiFetch('/api/bills');
  if (bills === null) return;
  renderBills(bills);
}

async function loadActions() {
  const actions = await apiFetch('/api/actions');
  if (actions === null) return;
  allActions = actions.sort(function(a, b) { return parseDate(b.date) - parseDate(a.date); });
  renderActions();
}

function renderBills(bills) {
  const list = document.getElementById('bill-list');
  if (bills.length === 0) {
    list.innerHTML = '<li style="color:var(--pico-muted-color);font-size:0.8rem">No bills tracked yet.</li>';
    document.getElementById('bill-filter').innerHTML = '<option value="">All Bills</option>';
    return;
  }

  // All values from the API are escaped before DOM insertion.
  list.innerHTML = bills.map(function(b) {
    var id = escapeHtml(b.id);
    return '<li><span>' + id + '</span>' +
      '<button class="remove-btn" title="Remove ' + id + '" onclick="removeBill(\'' + id + '\')">&times;</button>' +
      '</li>';
  }).join('');

  const filter = document.getElementById('bill-filter');
  const current = filter.value;
  filter.innerHTML = '<option value="">All Bills</option>' +
    bills.map(function(b) {
      var id = escapeHtml(b.id);
      return '<option value="' + id + '">' + id + '</option>';
    }).join('');
  if (current) filter.value = current;
}

function renderActions() {
  const filterId = document.getElementById('bill-filter').value;
  const rows = filterId ? allActions.filter(function(a) { return a.bill_id === filterId; }) : allActions;

  document.getElementById('action-count').textContent =
    rows.length + ' action' + (rows.length !== 1 ? 's' : '');

  const tbody = document.getElementById('actions-tbody');
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No actions found.</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(function(a) {
    return '<tr>' +
      '<td>' + escapeHtml(a.bill_id) + '</td>' +
      '<td>' + escapeHtml(a.date) + '</td>' +
      '<td>' + escapeHtml(a.chamber) + '</td>' +
      '<td>' + escapeHtml(a.description) + '</td>' +
      '</tr>';
  }).join('');
}

function applyFilter() {
  renderActions();
}

async function addBill() {
  const input = document.getElementById('add-bill-input');
  const errorEl = document.getElementById('add-error');
  const btn = document.getElementById('add-bill-btn');
  const billId = input.value.trim();
  if (!billId) return;

  errorEl.classList.add('hidden');
  btn.setAttribute('aria-busy', 'true');

  try {
    const res = await fetch('/api/bills', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bill_id: billId }),
    });

    if (res.status === 401) { window.location.href = '/login'; return; }

    if (res.ok) {
      input.value = '';
      await Promise.all([loadBills(), loadActions()]);
      showToast(billId.toUpperCase() + ' added', 'success');
    } else {
      const err = await res.json();
      errorEl.textContent = err.detail || 'Failed to add bill.';
      errorEl.classList.remove('hidden');
    }
  } finally {
    btn.removeAttribute('aria-busy');
  }
}

async function removeBill(billId) {
  if (!confirm('Remove ' + billId + ' from tracking? Its action history will also be deleted.')) return;

  const res = await fetch('/api/bills/' + billId, { method: 'DELETE' });
  if (res.status === 401) { window.location.href = '/login'; return; }

  if (res.ok) {
    await Promise.all([loadBills(), loadActions()]);
    showToast(billId + ' removed', 'success');
  } else {
    showToast('Failed to remove ' + billId, 'error');
  }
}

async function fetchUpdates() {
  const btn = document.getElementById('fetch-btn');
  btn.setAttribute('aria-busy', 'true');
  btn.textContent = 'Fetching...';

  try {
    const res = await fetch('/api/fetch', { method: 'POST' });
    if (res.status === 401) { window.location.href = '/login'; return; }

    if (!res.ok) {
      const err = await res.json();
      const msg = res.status === 429
        ? (err.detail || 'OpenStates rate limit reached - try again tomorrow.')
        : (err.detail || 'Fetch failed.');
      showToast(msg, 'error');
      return;
    }

    const result = await res.json();
    await loadActions();

    showToast(
      result.new_actions + ' new action' + (result.new_actions !== 1 ? 's' : '') +
      ' across ' + result.updated + ' bill' + (result.updated !== 1 ? 's' : ''),
      'success'
    );

    if (result.errors.length > 0) {
      showToast('Could not fetch: ' + result.errors.map(function(e) { return e.bill_id; }).join(', '), 'error');
    }

    setLastUpdated();
  } finally {
    btn.removeAttribute('aria-busy');
    btn.textContent = 'Fetch Updates';
  }
}

async function apiFetch(url) {
  try {
    const res = await fetch(url);
    if (res.status === 401) { window.location.href = '/login'; return null; }
    if (!res.ok) throw new Error(res.status + ' ' + res.statusText);
    return res.json();
  } catch (e) {
    showToast('Failed to load data: ' + e.message, 'error');
    return null;
  }
}

let toastTimer;
function showToast(message, type) {
  type = type || 'success';
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = 'toast ' + type;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function() { toast.classList.add('hidden'); }, 4000);
}

function setLastUpdated() {
  document.getElementById('last-updated').textContent =
    'Last fetched ' + new Date().toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit',
    });
}

function parseDate(str) {
  if (!str) return 0;
  return new Date(str).getTime() || 0;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
```

- [ ] **Step 4: Verify admin page end-to-end in browser**

With `uvicorn main:app --reload` and `ADMIN_PASSWORD=testpass` in `.env`:

1. Open `http://localhost:8000/admin` — redirects to `/login`
2. Log in with `testpass`
3. Admin page shows: "Admin" badge, "Fetch Updates" button, "Log out" link, add bill form, remove buttons
4. Add a bill (e.g., `HB1288`) — verify it appears in the sidebar
5. Click "Fetch Updates" — verify action count updates
6. Click "Log out" — redirects to public view
7. Open `http://localhost:8000` — public view shows bill list (no controls)

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add static/admin.html static/admin.js static/style.css
git commit -m "feat: add admin panel HTML and JS with write controls and session expiry handling"
```

---

## Task 6: Dockerfile and `.dockerignore`

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create `.dockerignore`**

```
.venv/
data/
.env
__pycache__/
*.pyc
*.pyo
.git/
.pytest_cache/
tests/
docs/
tracker.py
```

- [ ] **Step 3: Build the image**

```bash
docker build -t ilga-tracker .
```

Expected: build completes with no errors.

- [ ] **Step 4: Smoke-test the container**

```bash
docker run --rm -p 8000:8000 \
  -e OPENSTATES_API_KEY=test \
  -e ADMIN_PASSWORD=testpass \
  -e SECRET_KEY=dev-secret-key \
  ilga-tracker
```

Open `http://localhost:8000`. Verify the app loads. Stop with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "feat: add Dockerfile and .dockerignore for container deployment"
```

---

## Task 7: Fly.io deployment with `fly.toml`

**Files:**
- Create: `fly.toml`

- [ ] **Step 1: Install the Fly CLI**

```bash
brew install flyctl
```

Or on Linux/WSL:
```bash
curl -L https://fly.io/install.sh | sh
```

- [ ] **Step 2: Authenticate**

```bash
fly auth login
```

Creates a free account if you don't have one.

- [ ] **Step 3: Create the app**

```bash
fly launch --no-deploy
```

When prompted: choose app name (e.g., `ilga-tracker`), region `ord` (Chicago). Decline PostgreSQL and Redis.

This generates `fly.toml`. Replace its contents with:

```toml
app = 'ilga-tracker'
primary_region = 'ord'

[build]

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = 'off'
  auto_start_machines = true
  min_machines_running = 1
  processes = ['app']

[[vm]]
  memory = '256mb'
  cpu_kind = 'shared'
  cpus = 1

[mounts]
  source = 'tracker_data'
  destination = '/app/data'
```

Key settings explained:
- `auto_stop_machines = 'off'` + `min_machines_running = 1` — always-on, no cold starts
- `[mounts]` — persistent 1GB volume mounted at `/app/data` where SQLite lives
- `ord` — Chicago region, closest to Illinois state government users

- [ ] **Step 4: Create the persistent volume**

```bash
fly volumes create tracker_data --size 1 --region ord
```

Expected: `tracker_data` volume created. Free tier includes 3GB total.

- [ ] **Step 5: Set secrets**

Generate a strong SECRET_KEY first:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Then set all three secrets:
```bash
fly secrets set \
  OPENSTATES_API_KEY=<your-openstates-key> \
  ADMIN_PASSWORD=<strong-password-for-client> \
  SECRET_KEY=<output-from-above>
```

- [ ] **Step 6: Deploy**

```bash
fly deploy
```

Expected output ends with something like:
```
Visit your newly deployed app at https://ilga-tracker.fly.dev/
```

- [ ] **Step 7: Verify live deployment**

Open `https://ilga-tracker.fly.dev`:
1. Public view loads
2. `/login` shows password form
3. Log in as admin — admin panel works
4. Add a bill, fetch updates, log out

- [ ] **Step 8: Run one-time data migration (if needed)**

If you have existing data from the CSV:
```bash
fly ssh console
cd /app
python -m scripts.migrate --skip-api --csv legislative_tracker_updates.csv
exit
```

- [ ] **Step 9: Commit `fly.toml`**

```bash
git add fly.toml
git commit -m "feat: add fly.toml for Fly.io always-on deployment with persistent SQLite volume"
```

---

## Deployment Reference

Share this with the client:

| Item | Value |
|---|---|
| Public URL | `https://ilga-tracker.fly.dev` |
| Admin URL | `https://ilga-tracker.fly.dev/admin` |
| Login URL | `https://ilga-tracker.fly.dev/login` |
| Session length | 8 hours (re-login required each workday) |

**For you (developer only):**

Update app after code changes:
```bash
fly deploy
```

Change admin password:
```bash
fly secrets set ADMIN_PASSWORD=<new-password>
```

Check logs:
```bash
fly logs
```
