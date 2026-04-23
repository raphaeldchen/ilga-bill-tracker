import os
import pytest
import asyncpg
import pytest_asyncio

FAKE_BILL = {
    "title": "TEST BILL",
    "session": "104th",
    "actions": [
        {
            "date": "2025-01-15",
            "description": "First reading",
            "order": 1,
            "organization": {"classification": "lower", "name": "House"},
        }
    ],
}

TEST_DATABASE_URL = os.getenv("DATABASE_URL", "")


@pytest_asyncio.fixture
async def pool():
    """asyncpg connection pool. Skips if DATABASE_URL is not set."""
    if not TEST_DATABASE_URL:
        pytest.skip("DATABASE_URL not set")
    p = await asyncpg.create_pool(TEST_DATABASE_URL)
    yield p
    await p.close()
