"""
One-time migration: parse Legislative Tracker Bills.txt and seed the database.

Usage (from the ilga_tracker/ directory):

    # Full migration — fetches bill metadata from OpenStates (requires API key)
    python -m scripts.migrate

    # Import existing CSV only, skip OpenStates fetch (no API key needed)
    python -m scripts.migrate --skip-api --csv legislative_tracker_updates.csv

    # Custom file paths
    python -m scripts.migrate --bills-file path/to/bills.txt --csv path/to/updates.csv
"""

import sys
import csv
import re
import asyncio
import argparse
import sqlite3
from pathlib import Path

# Allow running as `python -m scripts.migrate` from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db, get_connection
from services.openstates import normalize_bill_id, fetch_bills, extract_chamber


def parse_bill_id_from_url(url: str) -> str | None:
    """
    Extract bill ID from an ILGA URL.
    'DocTypeID=HB&DocNum=1288' -> 'HB1288'
    """
    doc_type = re.search(r"DocTypeID=([A-Za-z]+)", url)
    doc_num = re.search(r"DocNum=(\d+)", url)
    if doc_type and doc_num:
        return f"{doc_type.group(1).upper()}{doc_num.group(1)}"
    return None


async def seed_from_openstates(bill_ids: list[str]) -> None:
    print(f"\nFetching {len(bill_ids)} bills from OpenStates...")
    results = await fetch_bills(bill_ids)

    with get_connection() as conn:
        for bill_id, data in results:
            if isinstance(data, Exception):
                print(f"  SKIP {bill_id}: {data}")
                continue

            conn.execute(
                "INSERT OR IGNORE INTO bills (id, title, session) VALUES (?, ?, ?)",
                (bill_id, data.get("title", ""), data.get("session", "")),
            )
            inserted = _insert_actions(conn, bill_id, data.get("actions", []))
            print(f"  OK   {bill_id}: {data.get('title', '')[:60]}  ({inserted} actions)")


def seed_from_csv(csv_path: Path) -> None:
    """
    Import legislative_tracker_updates.csv as the initial action cache.
    Useful for populating history before the OpenStates API key is available.
    """
    print(f"\nImporting actions from {csv_path}...")
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    with get_connection() as conn:
        bills_seen: set[str] = set()
        for order_num, row in enumerate(rows):
            bill_id = normalize_bill_id(row["Bill"])
            if bill_id not in bills_seen:
                conn.execute(
                    "INSERT OR IGNORE INTO bills (id, title, session) VALUES (?, ?, ?)",
                    (bill_id, row.get("Webpage Title", ""), "2025-2026"),
                )
                bills_seen.add(bill_id)
            conn.execute(
                """INSERT OR IGNORE INTO actions
                       (bill_id, date, chamber, description, order_num)
                   VALUES (?, ?, ?, ?, ?)""",
                (bill_id, row["Date"], row["Chamber"], row["Action"], order_num),
            )
    print(f"  Imported {len(rows)} rows for {len(bills_seen)} bills.")


def _insert_actions(
    conn: sqlite3.Connection, bill_id: str, actions: list[dict]
) -> int:
    inserted = 0
    for action in actions:
        cur = conn.execute(
            """INSERT OR IGNORE INTO actions
                   (bill_id, date, chamber, description, order_num)
               VALUES (?, ?, ?, ?, ?)""",
            (
                bill_id,
                action.get("date", ""),
                extract_chamber(action),
                action.get("description", ""),
                action.get("order", 0),
            ),
        )
        inserted += cur.rowcount
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the tracker database from existing files."
    )
    parser.add_argument(
        "--bills-file",
        default="Legislative Tracker Bills.txt",
        help="Path to the ILGA URL list (default: 'Legislative Tracker Bills.txt')",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Path to legislative_tracker_updates.csv to import as initial cache",
    )
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Skip the OpenStates API fetch (requires API key)",
    )
    args = parser.parse_args()

    init_db()

    # Parse bill IDs from the URL list
    bills_path = Path(args.bills_file)
    if not bills_path.exists():
        print(f"Error: bills file not found: {bills_path}")
        sys.exit(1)

    with open(bills_path, encoding="utf-8-sig") as f:
        lines = [l.strip() for l in f if l.strip()]

    bill_ids: list[str] = []
    for line in lines:
        if line.startswith("http"):
            bid = parse_bill_id_from_url(line)
            if bid:
                bill_ids.append(bid)
            else:
                print(f"  Could not parse URL: {line}")
        else:
            bill_ids.append(normalize_bill_id(line))

    print(f"Parsed {len(bill_ids)} bill IDs: {bill_ids}")

    # Optionally seed from CSV first (no API key needed)
    if args.csv:
        seed_from_csv(Path(args.csv))

    # Fetch live metadata + full action history from OpenStates
    if not args.skip_api:
        asyncio.run(seed_from_openstates(bill_ids))

    print("\nMigration complete.")


if __name__ == "__main__":
    main()
