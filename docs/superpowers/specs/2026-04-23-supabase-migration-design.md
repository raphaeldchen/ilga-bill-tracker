# Supabase Migration Design

**Date:** 2026-04-23
**Status:** Approved

## Problem

The app currently uses SQLite stored on a local volume. This means:
- Data lives on the developer's laptop (local storage burden)
- No colleague access without SSH or file sharing
- Single-writer constraint blocks multi-instance Fly.io deployments
- No web dashboard for inspecting data

## Goal

Migrate the database to Supabase (managed PostgreSQL) so that:
- Data is cloud-hosted and durable
- Both developers can access and inspect it from their own machines
- The app can scale to multiple Fly.io workers if needed

## Architecture

Replace `sqlite3` with `asyncpg` (PostgreSQL async driver). On FastAPI startup, a single `asyncpg` connection pool is created and stored on `app.state.pool`. All service functions acquire connections from that pool. The pool is closed on shutdown. `database.py` owns the pool lifecycle and schema creation.

The two-table schema (`bills`, `actions`) maps directly to PostgreSQL with minor DDL changes:
- `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
- `datetime('now')` default → `NOW()`
- `?` placeholders → `$1, $2, ...`
- `INSERT OR IGNORE` → `INSERT ... ON CONFLICT DO NOTHING`
- WAL/foreign key PRAGMAs → removed (Postgres handles these natively)

## Files Changed

| File | Change |
|------|--------|
| `config.py` | Add `DATABASE_URL` env var (Supabase connection string) |
| `database.py` | Replace sqlite3 connection/schema with asyncpg pool + Postgres DDL |
| `services/bills.py` | All queries become async, use pool, updated SQL syntax |
| `main.py` | Add lifespan handler to create/close pool on startup/shutdown |
| `scripts/migrate.py` | Add one-time SQLite→Supabase data export script |
| `requirements.txt` | Add `asyncpg` |
| Fly.io secrets | Add `DATABASE_URL`; volume mount can be removed |

`routers/` files are unchanged — they only call service functions.

## Data Migration

A one-time script reads all rows from the local `tracker.db` (SQLite) and inserts them into Supabase. After a successful migration, the local `data/tracker.db` file can be deleted and the Fly.io volume detached.

## Deployment

1. Create Supabase project, copy the connection string
2. Set `DATABASE_URL` as a Fly.io secret: `fly secrets set DATABASE_URL=...`
3. Deploy updated app: `fly deploy`
4. Run one-time data migration script
5. Verify data in Supabase dashboard
6. Remove Fly.io volume if all data confirmed migrated

## Environment Variables

| Variable | Where set | Description |
|----------|-----------|-------------|
| `DATABASE_URL` | `.env` (local), Fly.io secrets (prod) | Supabase PostgreSQL connection string |

## Out of Scope

- Connection pooling via PgBouncer (not needed at current scale)
- Row-level security / Supabase Auth (not needed; app manages its own auth)
- Real-time subscriptions (not needed)
