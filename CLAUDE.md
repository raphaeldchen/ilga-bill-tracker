# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A FastAPI backend that tracks Illinois legislative bills via the OpenStates API v3. It stores bill metadata and action history in SQLite and exposes a JSON REST API. The end goal is a client-facing web app; the frontend does not exist yet.

`tracker.py` is the original ILGA scraper (now broken due to ILGA site redesign) — kept for reference only.

The app is deployed on Fly.io at https://ilga-tracker.fly.dev. Public users see a read-only bill/actions view at `/`. Staff access a write-capable admin panel at `/admin` (password-protected via signed session cookie).

## Running the Server

```bash
python -m venv .venv && source .venv/bin/activate
# source .venv/bin/activate is required — pip/uvicorn are not on PATH otherwise
pip install -r requirements.txt
cp .env.example .env          # then fill in OPENSTATES_API_KEY
uvicorn main:app --reload
```

Interactive API docs: `http://localhost:8000/docs`

## Deployment (Fly.io)

```bash
fly deploy                    # deploy latest code
fly logs                      # stream live logs
fly ssh console               # open shell on the running machine
```

Required Fly secrets (set with `fly secrets set KEY=value`):
- `OPENSTATES_API_KEY` — OpenStates API key
- `ADMIN_PASSWORD` — password for the `/admin` panel
- `SECRET_KEY` — long random string for signing session cookies
- `SECURE_COOKIES=true` — must be set in production (ensures `Secure` flag on cookies)

The app runs a single uvicorn worker (no `--workers` flag). Multiple workers cause SQLite WAL contention.
Volume mounted at `/app/data` (matches `DB_PATH` in config.py — no config change needed).

## One-Time Migration

Seed the database from the existing bill list and CSV history (no API key needed for `--skip-api`):

```bash
# Import CSV history only (no API key required)
python -m scripts.migrate --skip-api --csv legislative_tracker_updates.csv

# Full migration once API key is set
python -m scripts.migrate --csv legislative_tracker_updates.csv
```

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/bills` | List tracked bills |
| POST | `/api/bills` | Add a bill `{"bill_id": "HB1288"}` |
| DELETE | `/api/bills/{bill_id}` | Remove a bill and its actions |
| GET | `/api/actions` | All cached actions (`?bill_id=HB1288` to filter) |
| GET | `/api/actions/export` | Download all actions as a JSON file |
| POST | `/api/fetch` | Pull latest updates from OpenStates for all tracked bills |

## Architecture

```
main.py                  FastAPI app, router wiring, DB init on startup
config.py                Env vars: OPENSTATES_API_KEY, DB path, IL session string
database.py              SQLite schema, connection helper, WAL mode

services/
  openstates.py          Async httpx client — all OpenStates API calls
  bills.py               Business logic: add/remove bills, fetch updates, query actions

routers/
  bills.py               /api/bills CRUD
  actions.py             /api/actions GET + export
  fetch.py               /api/fetch POST
  auth.py                /login GET+POST, /logout, /admin page — session cookie auth

scripts/
  migrate.py             One-time seed from Legislative Tracker Bills.txt + CSV

static/
  index.html / app.js    Public read-only view — no write controls
  admin.html / admin.js  Admin panel — all write actions, redirects to /login on 401
  login.html             Password form (POST /login)

data/tracker.db          SQLite database (gitignored)
```

**Auth:** `routers/auth.py` uses `itsdangerous.URLSafeTimedSerializer` for signed session cookies (8-hour expiry). `require_admin` FastAPI dependency guards all write routes (POST /api/bills, DELETE /api/bills/{id}, POST /api/fetch) and the /admin page. API write routes return 401 JSON; page routes redirect to /login.

**Key data flow for `POST /api/fetch`:**
`fetch_all_updates()` reads all bill IDs from DB → fires concurrent OpenStates requests via `asyncio.gather()` → upserts new actions with `INSERT OR IGNORE` on `UNIQUE(bill_id, order_num)` → returns `{updated, new_actions, errors}`.

**Bill ID normalization:** `normalize_bill_id()` in `services/openstates.py` uppercases and strips spaces (`"hb 1288"` → `"HB1288"`). `to_openstates_identifier()` re-inserts the space for the OpenStates API query (`"HB1288"` → `"HB 1288"`).

**IL session:** Hardcoded as `"104th"` in `config.py` (`IL_SESSION`). Update this when the 105th GA begins.
