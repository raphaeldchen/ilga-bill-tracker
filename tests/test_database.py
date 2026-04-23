import os
import pytest
from database import create_pool, close_pool, init_db, get_pool

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set"
)


@pytest.mark.asyncio
async def test_pool_creates_and_closes():
    await create_pool()
    pool = get_pool()
    assert pool is not None
    await close_pool()


@pytest.mark.asyncio
async def test_init_db_creates_tables():
    await create_pool()
    await init_db()
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name IN ('bills', 'actions')"
        )
    assert result == 2
    await close_pool()
