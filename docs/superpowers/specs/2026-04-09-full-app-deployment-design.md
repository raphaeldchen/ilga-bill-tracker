# Illinois Legislative Tracker — Full App Deployment Design

**Date:** 2026-04-09  
**Status:** Approved

## Summary

Deploy the existing FastAPI bill tracker as a publicly accessible web app for a single organization. Public users can view tracked bills and actions read-only. Staff access a password-protected admin interface to add/remove bills and trigger data fetches. Deployment targets Fly.io free tier with a persistent volume for SQLite.

---

## 1. Architecture

The existing FastAPI app is extended with three new concerns:

### Routes added

| Route | Method | Auth | Description |
|---|---|---|---|
| `/login` | GET | No | Serves login form |
| `/login` | POST | No | Validates password, sets session cookie |
| `/logout` | GET | No | Clears cookie, redirects to `/` |
| `/admin` | GET | Yes | Serves admin HTML page |

### API auth changes

| Route | Auth required? |
|---|---|
| `GET /api/bills` | No |
| `GET /api/actions` | No |
| `GET /api/actions/export` | No |
| `POST /api/bills` | Yes |
| `DELETE /api/bills/{id}` | Yes |
| `POST /api/fetch` | Yes |

### Static pages

- **`static/index.html`** — existing page, stripped of add/remove/fetch controls. Read-only: shows bill list and actions table.
- **`static/admin.html`** — new page with full controls: add bill, remove bill, fetch updates, logout link. Only reachable after login.
- **`static/login.html`** — new minimal login form (password field + submit). Inline error on failure.

### New router

`routers/auth.py` — handles `/login` GET+POST and `/logout`. No changes to existing routers except adding the auth dependency to write endpoints.

---

## 2. Auth Implementation

**Library:** `itsdangerous.URLSafeTimedSerializer` (already a transitive dependency via Starlette — no new package needed).

**Cookie:** Signed, max-age 8 hours. Checked via a FastAPI `Depends()` function `require_admin`.

**Credential storage:** `ADMIN_PASSWORD` env var (Fly secret). Never stored in the DB or repo.

**Behavior:**
- API write endpoints return `401 JSON` if cookie missing/invalid.
- `/admin` page route redirects to `/login` if cookie missing/invalid.
- Successful login redirects to `/admin`.
- Logout clears cookie and redirects to `/`.

**`SECRET_KEY` env var** — used to sign cookies. Must be a long random string. Set as a Fly secret.

---

## 3. Deployment (Fly.io)

### New files

**`Dockerfile`**
- Base: `python:3.12-slim`
- Working dir: `/app`
- Copies repo, installs `requirements.txt`, starts `uvicorn main:app --host 0.0.0.0 --port 8000`
- `data/` directory is empty in the image — overridden by the persistent volume at runtime

**`fly.toml`**
- App name: `ilga-tracker` (or similar)
- Internal port: `8000`
- Health check: `GET /`
- Volume mount: `/app/data`

**`.dockerignore`**
- Excludes: `.venv/`, `data/`, `.env`, `__pycache__/`, `*.pyc`, `.git/`

### One-time setup (developer only)

```bash
fly launch
fly volumes create tracker_data --size 1   # 1GB persistent disk, free tier
fly secrets set \
  OPENSTATES_API_KEY=<key> \
  ADMIN_PASSWORD=<password> \
  SECRET_KEY=<random-string>
fly deploy
```

### Ongoing updates

```bash
fly deploy   # after any code change
```

The client never runs any commands. They visit the assigned `https://<app>.fly.dev` URL.

### `DB_PATH` compatibility

`config.py` uses `Path(__file__).parent / "data" / "tracker.db"`. Inside the container the app is at `/app`, so this resolves to `/app/data/tracker.db` — matching the volume mount. No config change needed.

---

## 4. Future Considerations

- **Scheduled auto-fetch:** Can be added later as a Fly.io cron machine or an external cron service (e.g., cron-job.org hitting `POST /api/fetch` with an auth header). The current architecture does not need to change to support this.
- **Custom domain:** Fly supports custom domains with free TLS — a one-command addition when the org is ready.
- **Paid upgrade:** `fly scale vm shared-cpu-1x` or `fly scale memory 512` — no code changes required.
- **IL session update:** `IL_SESSION` in `config.py` is hardcoded as `"104th"`. Update to `"105th"` when the 105th GA begins and redeploy.

---

## 5. Out of Scope

- Individual user accounts or per-user bill lists
- Scheduled automatic fetching (deferred to future development)
- Email notifications or alerts
- Any frontend framework rewrite (existing vanilla JS stays)
