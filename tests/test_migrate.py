import csv
import pytest
from unittest.mock import patch
from scripts.migrate import parse_bill_id_from_url, seed_from_csv
from tests.conftest import FAKE_BILL


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


def test_seed_from_csv_inserts_bills(db, csv_file):
    with patch("scripts.migrate.get_connection", return_value=db):
        seed_from_csv(csv_file)

    bills = db.execute("SELECT id FROM bills ORDER BY id").fetchall()
    assert len(bills) == 2
    assert bills[0]["id"] == "HB1288"
    assert bills[1]["id"] == "SB0019"


def test_seed_from_csv_inserts_actions(db, csv_file):
    with patch("scripts.migrate.get_connection", return_value=db):
        seed_from_csv(csv_file)

    actions = db.execute("SELECT * FROM actions ORDER BY order_num").fetchall()
    assert len(actions) == 3
    assert actions[0]["bill_id"] == "HB1288"
    assert actions[0]["description"] == "First reading"
    assert actions[2]["bill_id"] == "SB0019"


def test_seed_from_csv_idempotent(db, csv_file):
    """Running seed_from_csv twice does not duplicate bills or actions."""
    with patch("scripts.migrate.get_connection", return_value=db):
        seed_from_csv(csv_file)
        seed_from_csv(csv_file)

    bill_count = db.execute("SELECT COUNT(*) FROM bills").fetchone()[0]
    action_count = db.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
    assert bill_count == 2
    assert action_count == 3
