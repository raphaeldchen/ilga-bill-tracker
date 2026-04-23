import pytest
import pytest_asyncio
from database import create_pool, close_pool, init_db, get_pool


@pytest.mark.asyncio
async def test_pool_creates_and_closes():
    """Test that pool can be created and closed."""
    await create_pool()
    pool = get_pool()
    assert pool is not None
    await close_pool()


@pytest.mark.asyncio
async def test_init_db_creates_tables():
    """Test that init_db creates bills and actions tables."""
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
