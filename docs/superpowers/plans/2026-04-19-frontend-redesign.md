# Frontend Redesign — Editorial Design System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the app's three pages (public view, admin, login) from plain PicoCSS defaults to a polished editorial aesthetic using a warm off-white palette, Illinois blue accent, and Playfair Display + Inter typography.

**Architecture:** Override PicoCSS v2 CSS custom properties at `:root` to establish the color and type system, then replace each CSS section with editorial-style rules. Chamber cells in dynamically-rendered table rows get a `chamberBadge()` JS helper added to both `app.js` and `admin.js`. Login page gets its inline styles moved to `style.css`.

**Tech Stack:** PicoCSS v2 (existing, kept), Google Fonts CDN (Playfair Display + Inter), vanilla JS (existing)

---

## File Map

| File | Change |
|---|---|
| `static/style.css` | Rewritten section-by-section across Tasks 1–6 |
| `static/index.html` | Add Google Fonts `<link>` tags |
| `static/admin.html` | Add Google Fonts `<link>` tags |
| `static/login.html` | Add Google Fonts `<link>`, restructure markup, remove inline `<style>` |
| `static/app.js` | Add `chamberBadge()` helper, update chamber cells in `renderActions` and `toggleExpand` |
| `static/admin.js` | Add `chamberBadge()` helper, update chamber cells in `renderActions` and `toggleExpand` |

---

## Task 1: Foundation — Google Fonts + CSS design tokens

**Files:**
- Modify: `static/index.html`
- Modify: `static/admin.html`
- Modify: `static/style.css`

- [ ] **Step 1: Add Google Fonts to index.html**

In `static/index.html`, replace the existing `<link>` block:
```html
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css" />
  <link rel="stylesheet" href="/static/style.css" />
```
with:
```html
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Playfair+Display:wght@400&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/static/style.css" />
```

- [ ] **Step 2: Add Google Fonts to admin.html**

In `static/admin.html`, make the identical replacement as Step 1.

- [ ] **Step 3: Add CSS design tokens to style.css**

At the very top of `static/style.css`, before the existing `/* ── Layout ──` comment, insert:
```css
/* ── Design tokens (PicoCSS overrides) ───────────────────────── */

:root {
  --pico-background-color: #faf9f7;
  --pico-color: #1a1a1a;
  --pico-muted-color: #6b6560;
  --pico-muted-border-color: #e0ddd8;
  --pico-primary: #003366;
  --pico-primary-hover: #00254d;
  --pico-primary-focus: rgba(0, 51, 102, 0.25);
  --pico-secondary-background: #f0ede8;
  --pico-del-color: #9b2335;
  --pico-font-family: 'Inter', system-ui, sans-serif;
  --pico-border-radius: 3px;
  --font-display: 'Playfair Display', Georgia, serif;
}

```

- [ ] **Step 4: Start the dev server and verify fonts load**

```bash
source .venv/bin/activate && uvicorn main:app --reload
```

Open `http://localhost:8000`. Expected: page background is warm off-white (`#faf9f7`), text is near-black, buttons are Illinois blue. Open DevTools Network tab — confirm `fonts.googleapis.com` requests succeed.

- [ ] **Step 5: Commit**

```bash
git add static/index.html static/admin.html static/style.css
git commit -m "feat: add Google Fonts and editorial CSS design tokens"
```

---

## Task 2: Header / Masthead

**Files:**
- Modify: `static/style.css`

- [ ] **Step 1: Replace header CSS**

In `static/style.css`, replace the entire `/* ── Layout ──` section's header-related rules. Find and replace this block (lines 1–49 of the existing layout section):
```css
.app-header {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--pico-background-color);
  border-bottom: 1px solid var(--pico-muted-border-color);
  padding: 0.75rem 1.5rem;
}

.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1400px;
  margin: 0 auto;
}

.header-title {
  display: flex;
  align-items: baseline;
  gap: 1rem;
}

.header-title strong {
  font-size: 1.1rem;
}

.last-updated {
  font-size: 0.8rem;
  color: var(--pico-muted-color);
}

.header-actions button {
  margin: 0;
}
```

with:
```css
.app-header {
  position: sticky;
  top: 0;
  z-index: 10;
  background: #ffffff;
  border-bottom: 1px solid var(--pico-muted-border-color);
  box-shadow: 0 2px 0 var(--pico-primary);
  padding: 0.85rem 1.5rem;
}

.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1400px;
  margin: 0 auto;
}

.header-title {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
}

.header-title strong {
  font-family: var(--font-display);
  font-size: 1.4rem;
  font-weight: 400;
  letter-spacing: -0.01em;
}

.last-updated {
  font-size: 0.75rem;
  color: var(--pico-muted-color);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.header-actions button,
.header-actions [role="button"] {
  margin: 0;
}
```

- [ ] **Step 2: Replace admin badge and logout button CSS**

Find and replace:
```css
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

with:
```css
.admin-badge {
  font-size: 0.6rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  background: var(--pico-primary);
  color: #fff;
  padding: 0.2rem 0.5rem;
  border-radius: 2px;
  vertical-align: middle;
}

.logout-btn {
  margin: 0;
  padding: 0.35rem 0.8rem;
  font-size: 0.82rem;
}
```

- [ ] **Step 3: Verify header appearance**

With the dev server running, open `http://localhost:8000`. Expected:
- Header has white background with a 2px Illinois blue bottom rule
- "Illinois Legislative Tracker" renders in Playfair Display (serif), ~1.4rem, normal weight
- Open `http://localhost:8000/admin` — "Admin" badge is a tight blue pill, Fetch Updates and Log out buttons are right-aligned

- [ ] **Step 4: Commit**

```bash
git add static/style.css
git commit -m "feat: editorial masthead header with Playfair Display title"
```

---

## Task 3: Sidebar

**Files:**
- Modify: `static/style.css`

- [ ] **Step 1: Replace sidebar CSS**

Find and replace the entire `/* ── Sidebar ──` section:
```css
/* ── Sidebar ─────────────────────────────────────────────────── */

.sidebar {
  border-right: 1px solid var(--pico-muted-border-color);
  padding: 1.25rem 1rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.sidebar h6 {
  margin: 0 0 0.5rem;
  text-transform: uppercase;
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  color: var(--pico-muted-color);
}

.bill-list {
  list-style: none;
  padding: 0;
  margin: 0;
  flex: 1;
}

.bill-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.3rem 0.4rem;
  border-radius: var(--pico-border-radius);
  font-size: 0.875rem;
  cursor: default;
}

.bill-list li:hover {
  background: var(--pico-secondary-background);
}

.remove-btn {
  background: none;
  border: none;
  color: var(--pico-muted-color);
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  padding: 0 0.2rem;
  margin: 0;
  width: auto;
}

.remove-btn:hover {
  color: var(--pico-del-color);
}

.add-bill-form {
  display: flex;
  gap: 0.4rem;
  margin-top: 0.5rem;
}

.add-bill-form input {
  margin: 0;
  font-size: 0.85rem;
  padding: 0.35rem 0.6rem;
  min-width: 0;
}

.add-btn {
  margin: 0;
  padding: 0.35rem 0.75rem;
  font-size: 0.85rem;
  white-space: nowrap;
}

.add-error {
  font-size: 0.78rem;
  color: var(--pico-del-color);
  margin: 0.25rem 0 0;
}
```

with:
```css
/* ── Sidebar ─────────────────────────────────────────────────── */

.sidebar {
  border-right: 1px solid var(--pico-muted-border-color);
  background: #ffffff;
  padding: 1.25rem 1rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.sidebar h6 {
  margin: 0 0 0.5rem;
  font-family: var(--font-display);
  font-size: 0.72rem;
  font-weight: 400;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--pico-muted-color);
}

.bill-list {
  list-style: none;
  padding: 0;
  margin: 0;
  flex: 1;
}

.bill-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.3rem 0.5rem;
  border-left: 2px solid transparent;
  font-size: 0.875rem;
  cursor: default;
  transition: border-color 0.12s;
}

.bill-list li:hover {
  background: none;
  border-left-color: var(--pico-primary);
}

.remove-btn {
  background: none;
  border: none;
  color: var(--pico-muted-color);
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  padding: 0 0.2rem;
  margin: 0;
  width: auto;
  transition: color 0.12s;
}

.remove-btn:hover {
  color: var(--pico-del-color);
}

.add-bill-form {
  display: flex;
  gap: 0.4rem;
  margin-top: 0.5rem;
  align-items: flex-end;
}

.add-bill-form input {
  margin: 0;
  font-size: 0.85rem;
  padding: 0.3rem 0;
  min-width: 0;
  border: none;
  border-bottom: 1px solid var(--pico-muted-border-color);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.add-bill-form input:focus {
  border-bottom-color: var(--pico-primary);
  outline: none;
  box-shadow: none;
}

.add-btn {
  margin: 0;
  padding: 0.3rem 0.7rem;
  font-size: 0.82rem;
  white-space: nowrap;
  border-radius: 2px;
}

.add-error {
  font-size: 0.78rem;
  color: var(--pico-del-color);
  margin: 0.25rem 0 0;
}
```

- [ ] **Step 2: Verify sidebar appearance**

Open `http://localhost:8000`. Expected:
- Sidebar has white background, visually distinct from the warm `#faf9f7` page background
- "Tracked Bills" label is in Playfair Display, uppercase, wider letter-spacing
- Hovering a bill item shows a blue left border flash, not a fill

Open `http://localhost:8000/admin`. Expected:
- Add bill input is flat (bottom-border only), no box
- Add button is a small blue rectangle

- [ ] **Step 3: Commit**

```bash
git add static/style.css
git commit -m "feat: editorial sidebar with Playfair section label and border hover"
```

---

## Task 4: Main Table + Chamber Badges

**Files:**
- Modify: `static/style.css`
- Modify: `static/app.js`
- Modify: `static/admin.js`

- [ ] **Step 1: Replace main content + table CSS**

Find and replace the entire `/* ── Main content ──` section:
```css
/* ── Main content ────────────────────────────────────────────── */

.main-content {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 1.25rem 1.5rem;
  gap: 0.75rem;
}

.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.action-count {
  font-size: 0.8rem;
  color: var(--pico-muted-color);
}

.table-toolbar select {
  margin: 0;
  width: auto;
  font-size: 0.85rem;
  padding: 0.3rem 0.6rem;
}

.table-wrap {
  flex: 1;
  overflow-y: auto;
  border: 1px solid var(--pico-muted-border-color);
  border-radius: var(--pico-border-radius);
}

.table-wrap table {
  margin: 0;
  border-collapse: collapse;
  width: 100%;
}

.table-wrap thead th {
  position: sticky;
  top: 0;
  background: var(--pico-background-color);
  border-bottom: 2px solid var(--pico-muted-border-color);
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  z-index: 1;
}

.table-wrap td, .table-wrap th {
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  vertical-align: top;
}

/* Bill ID column */
.table-wrap td:first-child {
  white-space: nowrap;
  font-family: var(--pico-font-family-monospace);
  font-size: 0.8rem;
  color: var(--pico-primary);
}

/* Date column */
.table-wrap td:nth-child(2) {
  white-space: nowrap;
  color: var(--pico-muted-color);
  font-size: 0.8rem;
}

/* Chamber column */
.table-wrap td:nth-child(3) {
  white-space: nowrap;
  font-size: 0.8rem;
}

.empty-state {
  text-align: center;
  color: var(--pico-muted-color);
  padding: 2rem !important;
}
```

with:
```css
/* ── Main content ────────────────────────────────────────────── */

.main-content {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 1.25rem 1.5rem;
  gap: 0.75rem;
}

.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.action-count {
  font-size: 0.78rem;
  font-variant: small-caps;
  letter-spacing: 0.04em;
  color: var(--pico-muted-color);
}

.table-toolbar select {
  margin: 0;
  width: auto;
  font-size: 0.85rem;
  padding: 0.3rem 0.6rem;
}

.table-wrap {
  flex: 1;
  overflow-y: auto;
  border: 1px solid var(--pico-muted-border-color);
  border-radius: var(--pico-border-radius);
  background: #ffffff;
}

.table-wrap table {
  margin: 0;
  border-collapse: collapse;
  width: 100%;
  background: #ffffff;
}

.table-wrap thead th {
  position: sticky;
  top: 0;
  background: #ffffff;
  border-bottom: 2px solid var(--pico-muted-border-color);
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--pico-primary);
  z-index: 1;
}

.table-wrap td, .table-wrap th {
  padding: 0.55rem 0.75rem;
  font-size: 0.875rem;
  vertical-align: top;
  border-bottom: 1px solid var(--pico-muted-border-color);
}

/* Bill ID column */
.table-wrap td:first-child {
  white-space: nowrap;
  font-family: var(--pico-font-family-monospace);
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--pico-primary);
}

/* Date column */
.table-wrap td:nth-child(2) {
  white-space: nowrap;
  color: var(--pico-muted-color);
  font-size: 0.8rem;
  font-variant-numeric: tabular-nums;
}

/* Chamber column */
.table-wrap td:nth-child(3) {
  white-space: nowrap;
  font-size: 0.8rem;
}

.chamber-badge {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--pico-primary);
  border: 1px solid var(--pico-primary);
  padding: 0.1rem 0.4rem;
  border-radius: 2px;
  white-space: nowrap;
}

tr.bill-row td:first-child::after {
  content: ' →';
  color: var(--pico-muted-color);
  font-family: var(--pico-font-family);
  font-weight: 400;
  font-size: 0.7rem;
  margin-left: 0.3rem;
}

.empty-state {
  text-align: center;
  color: var(--pico-muted-color);
  padding: 2rem !important;
}
```

- [ ] **Step 2: Add chamberBadge helper to app.js**

In `static/app.js`, add the following function directly before the `escapeHtml` function (at the bottom of the file):
```javascript
function chamberBadge(chamber) {
  return '<span class="chamber-badge">' + escapeHtml(chamber) + '</span>';
}
```

- [ ] **Step 3: Update renderActions in app.js to use chamberBadge**

In `static/app.js`, find the line in `renderActions` (line 83):
```javascript
      '<td>' + escapeHtml(a.chamber) + '</td>' +
```
Replace with:
```javascript
      '<td>' + chamberBadge(a.chamber) + '</td>' +
```

- [ ] **Step 4: Update toggleExpand in app.js to use chamberBadge**

In `static/app.js`, find the line in `toggleExpand`'s `historyRows` map (line 113):
```javascript
          '<td>' + escapeHtml(a.chamber) + '</td>' +
```
Replace with:
```javascript
          '<td>' + chamberBadge(a.chamber) + '</td>' +
```

- [ ] **Step 5: Add chamberBadge helper to admin.js**

In `static/admin.js`, add the following function directly before the `escapeHtml` function (at the bottom of the file):
```javascript
function chamberBadge(chamber) {
  return '<span class="chamber-badge">' + escapeHtml(chamber) + '</span>';
}
```

- [ ] **Step 6: Update renderActions in admin.js to use chamberBadge**

In `static/admin.js`, find the line in `renderActions` (line 89):
```javascript
      '<td>' + escapeHtml(a.chamber) + '</td>' +
```
Replace with:
```javascript
      '<td>' + chamberBadge(a.chamber) + '</td>' +
```

- [ ] **Step 7: Update toggleExpand in admin.js to use chamberBadge**

In `static/admin.js`, find the line in `toggleExpand`'s `historyRows` map (line 122):
```javascript
          '<td>' + escapeHtml(a.chamber) + '</td>' +
```
Replace with:
```javascript
          '<td>' + chamberBadge(a.chamber) + '</td>' +
```

- [ ] **Step 8: Verify table appearance**

Reload `http://localhost:8000`. Expected:
- Table header row: blue text (`#003366`), all-caps, wider letter-spacing
- Bill ID column: bold monospace blue, with a subtle `→` on clickable rows
- Date column: muted gray, numbers align cleanly
- Chamber column: `HOUSE` / `SENATE` rendered as outlined blue pills
- Thin `#e0ddd8` separator lines between rows (no zebra striping)

- [ ] **Step 9: Commit**

```bash
git add static/style.css static/app.js static/admin.js
git commit -m "feat: editorial table with chamber badges and blue column headers"
```

---

## Task 5: Expanded Row Panel

**Files:**
- Modify: `static/style.css`

- [ ] **Step 1: Replace expanded row CSS**

Find and replace the entire `/* -- Expanded bill row --` section:
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
  font-size: 0.7rem;
  font-family: var(--pico-font-family);
  margin: 0;
  border-collapse: collapse;
}

.expanded-history td,
.expanded-history th {
  padding: 0.12rem 0.4rem;
  line-height: 1.4;
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

with:
```css
/* ── Expanded bill row ───────────────────────────────────────── */

tr.bill-row {
  cursor: pointer;
}

tr.bill-row:hover td {
  background: var(--pico-secondary-background);
}

tr.expanded-row > td {
  padding: 0 0.75rem 0.75rem;
  background: var(--pico-background-color);
  border-bottom: 1px solid var(--pico-muted-border-color);
}

.expanded-content {
  border-left: 3px solid var(--pico-primary);
  background: #ffffff;
  border-radius: 0 var(--pico-border-radius) var(--pico-border-radius) 0;
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.expanded-content h6 {
  margin: 0 0 0.5rem;
  font-family: var(--font-display);
  font-size: 0.68rem;
  font-weight: 400;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--pico-muted-color);
}

.expanded-history table {
  width: 100%;
  font-size: 0.72rem;
  margin: 0;
  border-collapse: collapse;
}

.expanded-history td,
.expanded-history th {
  padding: 0.18rem 0.4rem;
  line-height: 1.4;
  border-bottom: 1px solid var(--pico-muted-border-color);
}

.expanded-history tr:last-child td {
  border-bottom: none;
}

.expanded-notes {
  border-top: 1px solid var(--pico-muted-border-color);
  padding-top: 1rem;
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
  border: 1px solid var(--pico-muted-border-color);
  border-radius: var(--pico-border-radius);
}

.save-note-btn {
  margin: 0;
  padding: 0.3rem 0.75rem;
  font-size: 0.82rem;
  border-radius: 2px;
}
```

- [ ] **Step 2: Verify expanded row appearance**

Reload `http://localhost:8000`. Click a bill row. Expected:
- Expanded panel appears below the clicked row with a `#003366` 3px left border
- "Action History" heading is Playfair Display, uppercase, muted
- History rows are tight, with thin separators; last row has no bottom border
- Notes section (if note exists) is separated by a thin rule with same Playfair label style

Open `http://localhost:8000/admin`, click a row. Expected:
- Same panel appears with an editable textarea and Save button

- [ ] **Step 3: Commit**

```bash
git add static/style.css
git commit -m "feat: editorial expanded row panel with blue left border accent"
```

---

## Task 6: Login Page

**Files:**
- Modify: `static/login.html`
- Modify: `static/style.css`

- [ ] **Step 1: Rewrite login.html**

Replace the entire contents of `static/login.html` with:
```html
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Admin Login - Illinois Legislative Tracker</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Playfair+Display:wght@400&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/static/style.css" />
</head>
<body class="login-page">
  <div class="login-card">
    <p class="login-masthead">Illinois Legislative Tracker</p>
    <p class="login-subtitle">Admin Login</p>

    <p class="login-error" id="error-msg">Incorrect password. Please try again.</p>

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

    <p class="login-back">
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

- [ ] **Step 2: Add login CSS to style.css**

At the end of `static/style.css`, append:
```css
/* ── Login page ──────────────────────────────────────────────── */

.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  margin: 0;
}

.login-card {
  width: 100%;
  max-width: 360px;
  background: #ffffff;
  border-top: 3px solid var(--pico-primary);
  padding: 2.5rem 2rem;
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.07);
}

.login-masthead {
  font-family: var(--font-display);
  font-size: 1.3rem;
  font-weight: 400;
  margin: 0 0 0.25rem;
  color: var(--pico-color);
}

.login-subtitle {
  color: var(--pico-muted-color);
  font-size: 0.85rem;
  margin-bottom: 2rem;
}

.login-card input[type="password"] {
  border: none;
  border-bottom: 1px solid var(--pico-muted-border-color);
  border-radius: 0;
  background: transparent;
  padding: 0.4rem 0;
  box-shadow: none;
}

.login-card input[type="password"]:focus {
  border-bottom-color: var(--pico-primary);
  outline: none;
  box-shadow: none;
}

.login-card button[type="submit"] {
  width: 100%;
  font-weight: 500;
  border-radius: 2px;
}

.login-error {
  color: var(--pico-del-color);
  font-size: 0.85rem;
  margin-bottom: 1rem;
  display: none;
}

.login-back {
  text-align: center;
  margin-top: 1.25rem;
  font-size: 0.8rem;
}
```

- [ ] **Step 3: Verify login page appearance**

Navigate to `http://localhost:8000/login`. Expected:
- Warm `#faf9f7` page background
- White card centered on page with a 3px `#003366` top border and subtle shadow
- "Illinois Legislative Tracker" in Playfair Display at ~1.3rem
- "Admin Login" in muted Inter below it
- Password input has bottom-border-only style (no box)
- "Sign in" button is full-width, blue
- "Back to public view" link is small and centered below

Test error state: navigate to `http://localhost:8000/login?error=1`. Expected: red error message appears above the form.

- [ ] **Step 4: Commit**

```bash
git add static/login.html static/style.css
git commit -m "feat: editorial login page with masthead card and flat input"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** All 6 design sections have a corresponding task. Color tokens (Task 1), header (Task 2), sidebar (Task 3), table + badges (Task 4), expanded row (Task 5), login (Task 6). ✓
- [x] **No placeholders:** All CSS blocks are complete. All JS changes show exact line context. ✓
- [x] **Type consistency:** `chamberBadge()` is defined and used identically in both `app.js` and `admin.js`. CSS class `.chamber-badge` matches the function's output. ✓
- [x] **Scope:** No backend changes, no new dependencies beyond Google Fonts CDN. ✓
