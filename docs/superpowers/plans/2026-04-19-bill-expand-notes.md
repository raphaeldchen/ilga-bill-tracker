# Bill Row Expand + Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clicking a bill row in the actions table expands it inline to show full action history and a notes section; notes are stored in SQLite, editable by admins, read-only for public users.

**Architecture:** Add a `note` column to `bills`, expose it via `GET /api/bills` and a new `PUT /api/bills/{id}/note` endpoint, then update both frontends to render an inline expanded row on click.

**Tech Stack:** FastAPI, SQLite, vanilla JS, PicoCSS

---

### Task 1: DB migration + service layer

**Files:**
- Modify: `database.py`
- Modify: `services/bills.py`
- Modify: `tests/test_bills_service.py`

- [ ] **Step 1: Write the failing service tests**

Add to `tests/test_bills_service.py`:

```python
from services.bills import update_bill_note


def test_update_bill_note(db):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test', '104th')")
    result = update_bill_note("HB1288", "This is a note")
    assert result is True
    row = db.execute("SELECT note FROM bills WHERE id = 'HB1288'").fetchone()
    assert row["note"] == "This is a note"


def test_update_bill_note_not_found(db):
    result = update_bill_note("HB9999", "note")
    assert result is False


def test_list_bills_includes_note(db):
    with db:
        db.execute("INSERT INTO bills (id, title, session, note) VALUES ('HB1288', 'Test', '104th', 'My note')")
    from services.bills import get_all_bills
    bills = get_all_bills()
    assert bills[0]["note"] == "My note"


def test_list_bills_note_defaults_empty(db):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test', '104th')")
    from services.bills import get_all_bills
    bills = get_all_bills()
    assert bills[0]["note"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_bills_service.py::test_update_bill_note tests/test_bills_service.py::test_update_bill_note_not_found tests/test_bills_service.py::test_list_bills_includes_note tests/test_bills_service.py::test_list_bills_note_defaults_empty -v
```

Expected: 4 FAILs — `update_bill_note` not defined, `note` not in select.

- [ ] **Step 3: Add `note` migration to `database.py`**

In `init_db()`, add this block immediately after the existing `last_fetched_at` migration block:

```python
        try:
            conn.execute("ALTER TABLE bills ADD COLUMN note TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass  # already exists
```

- [ ] **Step 4: Update `get_all_bills()` in `services/bills.py`**

Change the SELECT in `get_all_bills()` from:
```python
            "SELECT id, title, session, added_at FROM bills ORDER BY id"
```
to:
```python
            "SELECT id, title, session, added_at, note FROM bills ORDER BY id"
```

- [ ] **Step 5: Add `update_bill_note()` to `services/bills.py`**

Add after the `remove_bill` function:

```python
def update_bill_note(bill_id: str, note: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE bills SET note = ? WHERE id = ?", (note, bill_id)
        )
        return cur.rowcount > 0
```

- [ ] **Step 6: Run service tests to verify they pass**

```bash
pytest tests/test_bills_service.py::test_update_bill_note tests/test_bills_service.py::test_update_bill_note_not_found tests/test_bills_service.py::test_list_bills_includes_note tests/test_bills_service.py::test_list_bills_note_defaults_empty -v
```

Expected: 4 PASSes.

- [ ] **Step 7: Run full test suite to check for regressions**

```bash
pytest -v
```

Expected: all existing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add database.py services/bills.py tests/test_bills_service.py
git commit -m "feat: add note column to bills, expose in get_all_bills"
```

---

### Task 2: API route for updating notes

**Files:**
- Modify: `routers/bills.py`
- Modify: `tests/test_routes.py`

- [ ] **Step 1: Write the failing route tests**

Add to `tests/test_routes.py`:

```python
# -- PUT /api/bills/{bill_id}/note --------------------------------------------

def test_update_note_success(auth_client, db):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test Bill', '104th')")
    res = auth_client.put("/api/bills/HB1288/note", json={"note": "Important bill"})
    assert res.status_code == 200
    assert res.json() == {"bill_id": "HB1288", "note": "Important bill"}
    row = db.execute("SELECT note FROM bills WHERE id = 'HB1288'").fetchone()
    assert row["note"] == "Important bill"


def test_update_note_clears_note(auth_client, db):
    with db:
        db.execute("INSERT INTO bills (id, title, session, note) VALUES ('HB1288', 'Test', '104th', 'old note')")
    res = auth_client.put("/api/bills/HB1288/note", json={"note": ""})
    assert res.status_code == 200
    row = db.execute("SELECT note FROM bills WHERE id = 'HB1288'").fetchone()
    assert row["note"] == ""


def test_update_note_not_found_returns_404(auth_client):
    res = auth_client.put("/api/bills/HB9999/note", json={"note": "test"})
    assert res.status_code == 404


def test_update_note_requires_auth(client):
    res = client.put("/api/bills/HB1288/note", json={"note": "test"})
    assert res.status_code == 401


def test_list_bills_includes_note_field(client, db):
    with db:
        db.execute("INSERT INTO bills (id, title, session) VALUES ('HB1288', 'Test Bill', '104th')")
    res = client.get("/api/bills")
    assert res.status_code == 200
    assert "note" in res.json()[0]
    assert res.json()[0]["note"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_routes.py::test_update_note_success tests/test_routes.py::test_update_note_clears_note tests/test_routes.py::test_update_note_not_found_returns_404 tests/test_routes.py::test_update_note_requires_auth tests/test_routes.py::test_list_bills_includes_note_field -v
```

Expected: 5 FAILs.

- [ ] **Step 3: Add route to `routers/bills.py`**

Change the import line at the top of `routers/bills.py` from:
```python
from services.bills import get_all_bills, bill_exists, remove_bill, add_bill
```
to:
```python
from services.bills import get_all_bills, bill_exists, remove_bill, add_bill, update_bill_note
```

Add a new request model and route after the `delete_bill` route:

```python
class UpdateNoteRequest(BaseModel):
    note: str


@router.put("/{bill_id}/note", dependencies=[Depends(require_admin)])
def update_note(bill_id: str, body: UpdateNoteRequest) -> dict:
    normalized = normalize_bill_id(bill_id)
    if not update_bill_note(normalized, body.note):
        raise HTTPException(status_code=404, detail=f"{bill_id} not found")
    return {"bill_id": normalized, "note": body.note}
```

- [ ] **Step 4: Run route tests to verify they pass**

```bash
pytest tests/test_routes.py::test_update_note_success tests/test_routes.py::test_update_note_clears_note tests/test_routes.py::test_update_note_not_found_returns_404 tests/test_routes.py::test_update_note_requires_auth tests/test_routes.py::test_list_bills_includes_note_field -v
```

Expected: 5 PASSes.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add routers/bills.py tests/test_routes.py
git commit -m "feat: add PUT /api/bills/{id}/note route (admin-protected)"
```

---

### Task 3: CSS for expanded rows

**Files:**
- Modify: `static/style.css`

- [ ] **Step 1: Append expanded row styles to `static/style.css`**

```css
/* -- Expanded bill row ------------------------------------------------------ */

tr.bill-row {
  cursor: pointer;
}

tr.bill-row:hover td {
  background: var(--pico-secondary-background);
}

tr.expanded-row > td {
  padding: 0 0.75rem 0.75rem;
  background: var(--pico-secondary-background);
}

.expanded-content {
  border: 1px solid var(--pico-muted-border-color);
  border-radius: var(--pico-border-radius);
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.expanded-content h6 {
  margin: 0 0 0.4rem;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--pico-muted-color);
}

.expanded-history table {
  width: 100%;
  font-size: 0.8rem;
  margin: 0;
  border-collapse: collapse;
}

.expanded-history td,
.expanded-history th {
  padding: 0.25rem 0.5rem;
}

.note-text {
  font-size: 0.875rem;
  white-space: pre-wrap;
  margin: 0;
}

.expanded-notes textarea {
  width: 100%;
  font-size: 0.85rem;
  margin: 0 0 0.5rem;
  min-height: 80px;
  box-sizing: border-box;
}

.save-note-btn {
  margin: 0;
  padding: 0.3rem 0.75rem;
  font-size: 0.85rem;
}
```

- [ ] **Step 2: Commit**

```bash
git add static/style.css
git commit -m "feat: add CSS for inline expanded bill rows"
```

---

### Task 4: Public frontend (app.js) -- row expand with read-only notes

**Files:**
- Modify: `static/app.js`

All innerHTML assignments below are safe: every value is passed through escapeHtml() before insertion.

- [ ] **Step 1: Add `allBills` store and update `loadBills()`**

Change the top of `app.js` from:
```javascript
let allActions = [];
let collapsedView = true;  // show one row per bill by default
```
to:
```javascript
let allActions = [];
let allBills = [];
let collapsedView = true;  // show one row per bill by default
```

Change `loadBills()` from:
```javascript
async function loadBills() {
  const bills = await apiFetch('/api/bills');
  if (bills === null) return;
  renderBills(bills);
}
```
to:
```javascript
async function loadBills() {
  const bills = await apiFetch('/api/bills');
  if (bills === null) return;
  allBills = bills;
  renderBills(bills);
}
```

- [ ] **Step 2: Replace `renderActions()` with collapse + click version**

Replace the entire `renderActions()` function with:

```javascript
function renderActions() {
  document.querySelectorAll('tr.expanded-row').forEach(function(r) { r.remove(); });

  const filterId = document.getElementById('bill-filter').value;
  let rows = filterId ? allActions.filter(function(a) { return a.bill_id === filterId; }) : allActions;

  if (collapsedView && !filterId) rows = latestActionPerBill(rows);

  document.getElementById('action-count').textContent =
    rows.length + (collapsedView && !filterId ? ' bill' : ' action') + (rows.length !== 1 ? 's' : '');

  const tbody = document.getElementById('actions-tbody');
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No actions found.</td></tr>';
    return;
  }

  const clickable = collapsedView && !filterId;
  tbody.innerHTML = rows.map(function(a) {
    var billId = escapeHtml(a.bill_id);
    var rowAttrs = clickable
      ? ' class="bill-row" data-bill-id="' + billId + '" onclick="toggleExpand(\'' + billId + '\')"'
      : '';
    return '<tr' + rowAttrs + '>' +
      '<td>' + billId + '</td>' +
      '<td>' + escapeHtml(a.date) + '</td>' +
      '<td>' + escapeHtml(a.chamber) + '</td>' +
      '<td>' + escapeHtml(a.description) + '</td>' +
      '</tr>';
  }).join('');
}
```

- [ ] **Step 3: Add `toggleExpand()` after `applyFilter()`**

```javascript
function toggleExpand(billId) {
  const existing = document.querySelector('tr.expanded-row[data-expanded-for="' + billId + '"]');
  if (existing) {
    existing.remove();
    return;
  }

  document.querySelectorAll('tr.expanded-row').forEach(function(r) { r.remove(); });

  const billRow = document.querySelector('tr.bill-row[data-bill-id="' + billId + '"]');
  if (!billRow) return;

  const bill = allBills.find(function(b) { return b.id === billId; });
  const billActions = allActions
    .filter(function(a) { return a.bill_id === billId; })
    .slice()
    .reverse();

  var historyRows = billActions.length
    ? billActions.map(function(a) {
        return '<tr>' +
          '<td>' + escapeHtml(a.date) + '</td>' +
          '<td>' + escapeHtml(a.chamber) + '</td>' +
          '<td>' + escapeHtml(a.description) + '</td>' +
          '</tr>';
      }).join('')
    : '<tr><td colspan="3" class="empty-state">No actions.</td></tr>';

  var noteHtml = '';
  if (bill && bill.note) {
    noteHtml = '<div class="expanded-notes">' +
      '<h6>Notes</h6>' +
      '<p class="note-text">' + escapeHtml(bill.note) + '</p>' +
      '</div>';
  }

  var expandedRow = document.createElement('tr');
  expandedRow.className = 'expanded-row';
  expandedRow.setAttribute('data-expanded-for', billId);
  expandedRow.innerHTML = '<td colspan="4"><div class="expanded-content">' +
    '<div class="expanded-history"><h6>Action History</h6>' +
    '<table><thead><tr><th>Date</th><th>Chamber</th><th>Action</th></tr></thead>' +
    '<tbody>' + historyRows + '</tbody></table></div>' +
    noteHtml +
    '</div></td>';

  billRow.insertAdjacentElement('afterend', expandedRow);
}
```

- [ ] **Step 4: Manual test**

Start server: `uvicorn main:app --reload`

Open `http://localhost:8000`. Verify:
- Table shows one row per bill.
- Clicking a row expands inline action history (oldest-first) below it.
- Clicking the same row again collapses it.
- Clicking a different row collapses the previous and expands the new one.
- Bills with a note show it; bills without a note show no notes section.

- [ ] **Step 5: Commit**

```bash
git add static/app.js
git commit -m "feat: expand bill row inline on click (public view, read-only notes)"
```

---

### Task 5: Admin frontend (admin.js) -- collapsed view + editable notes

**Files:**
- Modify: `static/admin.js`

All innerHTML assignments below are safe: every value is passed through escapeHtml() before insertion.

- [ ] **Step 1: Add state variables**

Change the top of `admin.js` from:
```javascript
let allActions = [];
```
to:
```javascript
let allActions = [];
let allBills = [];
let collapsedView = true;
```

- [ ] **Step 2: Add `latestActionPerBill()` after `renderBills()`**

```javascript
function latestActionPerBill(actions) {
  const seen = new Set();
  return actions.filter(function(a) {
    if (seen.has(a.bill_id)) return false;
    seen.add(a.bill_id);
    return true;
  });
}
```

- [ ] **Step 3: Update `loadBills()` to store bills**

Change `loadBills()` from:
```javascript
async function loadBills() {
  const bills = await apiFetch('/api/bills');
  if (bills === null) return;
  renderBills(bills);
}
```
to:
```javascript
async function loadBills() {
  const bills = await apiFetch('/api/bills');
  if (bills === null) return;
  allBills = bills;
  renderBills(bills);
}
```

- [ ] **Step 4: Replace `renderActions()` with collapse + click version**

Replace the entire `renderActions()` function with:

```javascript
function renderActions() {
  document.querySelectorAll('tr.expanded-row').forEach(function(r) { r.remove(); });

  const filterId = document.getElementById('bill-filter').value;
  let rows = filterId ? allActions.filter(function(a) { return a.bill_id === filterId; }) : allActions;

  if (collapsedView && !filterId) rows = latestActionPerBill(rows);

  document.getElementById('action-count').textContent =
    rows.length + (collapsedView && !filterId ? ' bill' : ' action') + (rows.length !== 1 ? 's' : '');

  const tbody = document.getElementById('actions-tbody');
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No actions found.</td></tr>';
    return;
  }

  const clickable = collapsedView && !filterId;
  tbody.innerHTML = rows.map(function(a) {
    var billId = escapeHtml(a.bill_id);
    var rowAttrs = clickable
      ? ' class="bill-row" data-bill-id="' + billId + '" onclick="toggleExpand(\'' + billId + '\')"'
      : '';
    return '<tr' + rowAttrs + '>' +
      '<td>' + billId + '</td>' +
      '<td>' + escapeHtml(a.date) + '</td>' +
      '<td>' + escapeHtml(a.chamber) + '</td>' +
      '<td>' + escapeHtml(a.description) + '</td>' +
      '</tr>';
  }).join('');
}
```

- [ ] **Step 5: Add `toggleExpand()` and `saveNote()` after `applyFilter()`**

```javascript
function toggleExpand(billId) {
  const existing = document.querySelector('tr.expanded-row[data-expanded-for="' + billId + '"]');
  if (existing) {
    existing.remove();
    return;
  }

  document.querySelectorAll('tr.expanded-row').forEach(function(r) { r.remove(); });

  const billRow = document.querySelector('tr.bill-row[data-bill-id="' + billId + '"]');
  if (!billRow) return;

  const bill = allBills.find(function(b) { return b.id === billId; });
  const billActions = allActions
    .filter(function(a) { return a.bill_id === billId; })
    .slice()
    .reverse();

  var historyRows = billActions.length
    ? billActions.map(function(a) {
        return '<tr>' +
          '<td>' + escapeHtml(a.date) + '</td>' +
          '<td>' + escapeHtml(a.chamber) + '</td>' +
          '<td>' + escapeHtml(a.description) + '</td>' +
          '</tr>';
      }).join('')
    : '<tr><td colspan="3" class="empty-state">No actions.</td></tr>';

  var currentNote = bill ? (bill.note || '') : '';
  var safeId = escapeHtml(billId);
  var noteHtml = '<div class="expanded-notes">' +
    '<h6>Notes</h6>' +
    '<textarea id="note-' + safeId + '">' + escapeHtml(currentNote) + '</textarea>' +
    '<button class="save-note-btn" onclick="saveNote(\'' + safeId + '\')">Save</button>' +
    '</div>';

  var expandedRow = document.createElement('tr');
  expandedRow.className = 'expanded-row';
  expandedRow.setAttribute('data-expanded-for', billId);
  expandedRow.innerHTML = '<td colspan="4"><div class="expanded-content">' +
    '<div class="expanded-history"><h6>Action History</h6>' +
    '<table><thead><tr><th>Date</th><th>Chamber</th><th>Action</th></tr></thead>' +
    '<tbody>' + historyRows + '</tbody></table></div>' +
    noteHtml +
    '</div></td>';

  billRow.insertAdjacentElement('afterend', expandedRow);
}

async function saveNote(billId) {
  const textarea = document.getElementById('note-' + billId);
  if (!textarea) return;
  const note = textarea.value;

  const res = await fetch('/api/bills/' + billId + '/note', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note: note }),
  });

  if (res.status === 401) { window.location.href = '/login'; return; }

  if (res.ok) {
    const bill = allBills.find(function(b) { return b.id === billId; });
    if (bill) bill.note = note;
    showToast('Note saved', 'success');
  } else {
    showToast('Failed to save note', 'error');
  }
}
```

- [ ] **Step 6: Manual test**

Open `http://localhost:8000/admin`. Verify:
- Table shows one row per bill (collapsed).
- Clicking a row expands it with action history and a notes textarea.
- Typing a note and clicking Save shows "Note saved" toast.
- Reloading and re-expanding the bill shows the saved note.
- Opening `/` and expanding the same bill shows the note read-only.

- [ ] **Step 7: Commit**

```bash
git add static/admin.js
git commit -m "feat: expand bill row inline on click (admin view, editable notes)"
```
