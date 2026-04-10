# Functional Test Suite Design

**Date:** 2026-04-07
**Scope:** Integration/functional tests for the Illinois Legislative Tracker FastAPI backend

---

## Overview

A pytest-based functional test suite covering utility functions, business logic, and HTTP routes. Tests use an in-memory SQLite database and mock the OpenStates API at the `fetch_bills` function level — no network calls, no API quota consumed.

---

## Architecture

### File Structure

```
tests/
  __init__.py
  conftest.py              # shared fixtures
  test_utils.py            # pure utility function tests
  test_bills_service.py    # service layer: caching, fetch/upsert, add_bill, get_actions
  test_routes.py           # HTTP endpoint tests for all API routes
```

### New Dependencies

Added to `requirements.txt`:
- `pytest` — test runner
- `pytest-asyncio` — async test support for service layer tests

---

## Fixtures (`conftest.py`)

### `db` fixture
- Creates a fresh `sqlite3.connect(":memory:")` connection per test
- Applies the full schema (bills + actions tables, foreign keys)
- Patches `database.get_connection` to return this connection for the duration of the test
- All service calls use the in-memory DB transparently — no code changes needed in production code
- Closes the connection on teardown

### `client` fixture
- Depends on `db`
- Wraps the FastAPI app in a `TestClient` with the DB patch already in place
- Handles the app lifespan (startup `init_db()` runs against in-memory DB safely)
- Route tests use `client.get(...)`, `client.post(...)` etc.

### `mock_openstates` fixture
- Patches `services.bills.fetch_bills` using `unittest.mock.patch`
- Accepts a list of fake bill dicts to return
- Tests that don't touch OpenStates ignore it; tests that exercise fetch paths configure it per-test

---

## Test Coverage

### `test_utils.py` — Pure functions, no fixtures

| Test | What it verifies |
|------|-----------------|
| `test_normalize_lowercase` | `"hb 1288"` → `"HB1288"` |
| `test_normalize_spaces` | `"HB 1288"` → `"HB1288"` |
| `test_normalize_mixed` | `"sB0086"` → `"SB0086"` |
| `test_to_openstates_identifier` | `"HB1288"` → `"HB 1288"` |
| `test_to_openstates_identifier_no_match` | Non-standard ID passes through unchanged |
| `test_extract_chamber_lower` | `"lower"` classification → `"House"` |
| `test_extract_chamber_upper` | `"upper"` classification → `"Senate"` |
| `test_extract_chamber_fallback` | Unknown classification → returns raw value or `"Unknown"` |

### `test_bills_service.py` — Uses `db` + `mock_openstates`

| Test | What it verifies |
|------|-----------------|
| `test_add_bill_success` | Inserts bill row and all actions; returns correct metadata |
| `test_add_bill_not_found` | Raises exception when OpenStates returns no results |
| `test_get_actions_all` | Returns all actions across all bills |
| `test_get_actions_filtered` | Filters correctly by `bill_id` |
| `test_fetch_skips_recent_bills` | Bills with `last_fetched_at` < 12 hours ago are excluded; `fetch_bills` not called |
| `test_fetch_stale_bills` | Bills with `last_fetched_at` older than 12 hours are fetched |
| `test_fetch_null_last_fetched` | Bills with `last_fetched_at IS NULL` are always fetched |
| `test_fetch_stamps_last_fetched_at` | Successful fetch updates `last_fetched_at` on the bill row |
| `test_fetch_upserts_actions` | New actions are inserted; duplicate `(bill_id, order_num)` pairs are ignored |
| `test_fetch_partial_errors` | Failed bills appear in `errors` list; successful bills still update |
| `test_fetch_empty_db` | Returns `{updated: 0, new_actions: 0, errors: []}` immediately; no API call |
| `test_fetch_all_cached` | All bills fresh → returns skipped message; no API call |

### `test_routes.py` — Uses `client`

| Test | What it verifies |
|------|-----------------|
| `test_list_bills_empty` | `GET /api/bills` returns `[]` on empty DB |
| `test_list_bills` | Returns tracked bills after adding some |
| `test_add_bill_route` | `POST /api/bills` with valid ID returns 200 + bill metadata |
| `test_add_bill_duplicate` | `POST /api/bills` with existing ID returns 400 |
| `test_add_bill_invalid` | `POST /api/bills` with unknown ID returns 4xx |
| `test_remove_bill` | `DELETE /api/bills/{id}` removes bill and its actions |
| `test_remove_bill_not_found` | `DELETE /api/bills/{id}` for unknown ID returns 404 |
| `test_get_actions` | `GET /api/actions` returns all cached actions |
| `test_get_actions_filter` | `GET /api/actions?bill_id=HB1288` filters correctly |
| `test_fetch_updates_success` | `POST /api/fetch` returns `{updated, new_actions, errors}` |
| `test_fetch_updates_rate_limit` | `POST /api/fetch` returns 429 when OpenStates rate-limits |

---

## Key Design Decisions

**Mock at `fetch_bills`, not at the HTTP layer.** The httpx client in `services/openstates.py` is thin — just a GET request and some JSON parsing. The testable logic lives in `services/bills.py`. Mocking `fetch_bills` directly keeps tests fast and avoids crafting HTTP responses.

**Patching `get_connection` at the module level.** Since `get_connection()` returns a plain `sqlite3.Connection` (which is already a context manager), the in-memory connection drops in as a seamless replacement. No changes to production code.

**Per-test isolation.** Each test gets its own `db` fixture instance — a fresh in-memory DB with the schema applied. Tests cannot interfere with each other.

**No `--skip-api` equivalent needed.** Because the mock intercepts at the function level, tests never need an API key set.
