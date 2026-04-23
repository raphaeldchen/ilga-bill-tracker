import asyncpg
from config import DATABASE_URL

_pool: asyncpg.Pool | None = None


async def create_pool() -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, statement_cache_size=0)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    assert _pool is not None, "Database pool not initialized — call create_pool() first"
    return _pool


async def init_db() -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bills (
                id              TEXT PRIMARY KEY,
                title           TEXT,
                session         TEXT,
                added_at        TEXT DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS'),
                last_fetched_at TEXT,
                note            TEXT NOT NULL DEFAULT '',
                source_url      TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS actions (
                id          SERIAL PRIMARY KEY,
                bill_id     TEXT    NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
                date        TEXT,
                chamber     TEXT,
                description TEXT,
                order_num   INTEGER,
                UNIQUE(bill_id, order_num)
            );
        """)
