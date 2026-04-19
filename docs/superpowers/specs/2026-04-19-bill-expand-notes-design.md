# Bill Row Expand + Notes — Design Spec

## Overview

Clicking a bill row in the actions table expands it inline to show full action history and a notes section. Notes are stored in SQLite and served via the existing `/api/bills` response. Public view shows notes read-only; admin view allows editing.

---

## Data Model

Add `note TEXT NOT NULL DEFAULT ''` column to the `bills` table.

Migration in `database.py` `init_db()` (same pattern as the existing `last_fetched_at` migration):

```python
try:
    conn.execute("ALTER TABLE bills ADD COLUMN note TEXT NOT NULL DEFAULT ''")
except Exception:
    pass  # already exists
```

---

## Backend Changes

### `services/bills.py`

1. `get_all_bills()` — add `note` to the SELECT: `SELECT id, title, session, added_at, note FROM bills ORDER BY id`
2. New function `update_bill_note(bill_id: str, note: str) -> bool` — `UPDATE bills SET note = ? WHERE id = ?`, returns `True` if rowcount > 0.

### `routers/bills.py`

New route, admin-protected:

```
PUT /api/bills/{bill_id}/note
Body: { "note": "..." }
Response 200: { "bill_id": "...", "note": "..." }
Response 404: bill not found
```

Uses `require_admin` dependency. Calls `update_bill_note()`.

---

## Frontend Changes

### Both `app.js` and `admin.js`

**Store bills in memory.** Add `let allBills = []` (parallel to `allActions`). In `loadBills()`, save the response: `allBills = bills` before calling `renderBills(bills)`. This lets row-click handlers look up `note` by `bill_id` without an extra fetch.

**Collapsed view in admin.js.** The `collapsedView` logic added to `app.js` is not yet in `admin.js`. Add the same `collapsedView = true` flag and `latestActionPerBill()` helper to `admin.js` so both views are consistent.

**Row click → expand/collapse.** In `renderActions()`, each `<tr>` for a bill row gets:
- `data-bill-id` attribute
- `style="cursor:pointer"` 
- An `onclick` wired to `toggleExpand(billId)`

`toggleExpand(billId)`:
- If an expanded row for this bill already exists in the DOM, remove it (collapse).
- Otherwise, collapse any currently expanded row, then insert a new `<tr class="expanded-row">` immediately after the clicked row.

**Expanded row contents:**

```
[ Action History ]
Sub-table with columns: Date | Chamber | Action
Rows: all actions for this bill from allActions, sorted oldest-first (order_num ascending, i.e. reversed from allActions which is newest-first).

[ Notes ]
- Public view (app.js): show note text if non-empty, else show nothing.
- Admin view (admin.js): always show a <textarea> pre-filled with current note + Save button.
```

**Save note (admin.js only).** Save button calls `saveNote(billId, textareaValue)`:
- `PUT /api/bills/{billId}/note` with `{ note: value }`
- On 401: redirect to `/login`
- On success: update `allBills` entry in memory, show toast "Note saved", leave expanded row open
- On error: show error toast

---

## File Checklist

| File | Change |
|------|--------|
| `database.py` | `ALTER TABLE` migration for `note` column |
| `services/bills.py` | Add `note` to `get_all_bills()` SELECT; add `update_bill_note()` |
| `routers/bills.py` | Add `PUT /{bill_id}/note` route |
| `static/app.js` | Store `allBills`; add row click + expand; read-only note display |
| `static/admin.js` | Same as app.js + `collapsedView` logic + editable textarea + save |

---

## Out of Scope

- Note history / versioning
- Per-user notes
- Rich text / markdown in notes
