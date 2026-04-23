import csv
import pytest
import pytest_asyncio
import database
from scripts.migrate import parse_bill_id_from_url, seed_from_csv


# ── parse_bill_id_from_url ────────────────────────────────────────────────────

def test_parse_hb_url():
    url = "https://www.ilga.gov/legislation/BillStatus.asp?DocTypeID=HB&DocNum=1288&GAID=17"
    assert parse_bill_id_from_url(url) == "HB1288"


def test_parse_sb_url():
    url = "https://www.ilga.gov/legislation/BillStatus.asp?DocTypeID=SB&DocNum=0086&GAID=17"
    assert parse_bill_id_from_url(url) == "SB0086"


def test_parse_missing_doc_type():
    url = "https://www.ilga.gov/legislation/BillStatus.asp?DocNum=1288"
    assert parse_bill_id_from_url(url) is None


def test_parse_missing_doc_num():
    url = "https://www.ilga.gov/legislation/BillStatus.asp?DocTypeID=HB"
    assert parse_bill_id_from_url(url) is None


def test_parse_empty_string():
    assert parse_bill_id_from_url("") is None


# ── seed_from_csv ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def setup_db(pool):
    database._pool = pool
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bills (
                id TEXT PRIMARY KEY, title TEXT, session TEXT,
                added_at TEXT DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS'),
                last_fetched_at TEXT, note TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS actions (
                id SERIAL PRIMARY KEY, bill_id TEXT NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
                date TEXT, chamber TEXT, description TEXT, order_num INTEGER,
                UNIQUE(bill_id, order_num)
            );
        """)
    yield
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS actions; DROP TABLE IF EXISTS bills;")
    database._pool = None


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "test_updates.csv"
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["Bill", "Date", "Chamber", "Action", "Webpage Title"]
        )
        writer.writeheader()
        writer.writerow({"Bill": "HB1288", "Date": "1/15/2025", "Chamber": "House",
                         "Action": "First reading", "Webpage Title": "SOME BILL"})
        writer.writerow({"Bill": "HB1288", "Date": "1/20/2025", "Chamber": "House",
                         "Action": "Second reading", "Webpage Title": "SOME BILL"})
        writer.writerow({"Bill": "SB0019", "Date": "1/16/2025", "Chamber": "Senate",
                         "Action": "First reading", "Webpage Title": "OTHER BILL"})
    return path


@pytest.mark.asyncio
async def test_seed_from_csv_inserts_bills(csv_file, pool):
    await seed_from_csv(csv_file)
    async with pool.acquire() as conn:
        bills = await conn.fetch("SELECT id FROM bills ORDER BY id")
    assert len(bills) == 2
    assert bills[0]["id"] == "HB1288"
    assert bills[1]["id"] == "SB0019"


@pytest.mark.asyncio
async def test_seed_from_csv_inserts_actions(csv_file, pool):
    await seed_from_csv(csv_file)
    async with pool.acquire() as conn:
        actions = await conn.fetch("SELECT * FROM actions ORDER BY order_num")
    assert len(actions) == 3
    assert actions[0]["bill_id"] == "HB1288"
    assert actions[0]["description"] == "First reading"
    assert actions[2]["bill_id"] == "SB0019"


@pytest.mark.asyncio
async def test_seed_from_csv_idempotent(csv_file, pool):
    """Running seed_from_csv twice does not duplicate bills or actions."""
    await seed_from_csv(csv_file)
    await seed_from_csv(csv_file)
    async with pool.acquire() as conn:
        bill_count = await conn.fetchval("SELECT COUNT(*) FROM bills")
        action_count = await conn.fetchval("SELECT COUNT(*) FROM actions")
    assert bill_count == 2
    assert action_count == 3
