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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import create_pool, close_pool, init_db, get_pool
from services.openstates import normalize_bill_id, fetch_bills, extract_chamber


def parse_bill_id_from_url(url: str) -> str | None:
    doc_type = re.search(r"DocTypeID=([A-Za-z]+)", url)
    doc_num = re.search(r"DocNum=(\d+)", url)
    if doc_type and doc_num:
        return f"{doc_type.group(1).upper()}{doc_num.group(1)}"
    return None


async def seed_from_openstates(bill_ids: list[str]) -> None:
    print(f"\nFetching {len(bill_ids)} bills from OpenStates...")
    results = await fetch_bills(bill_ids)

    async with get_pool().acquire() as conn:
        for bill_id, data in results:
            if isinstance(data, Exception):
                print(f"  SKIP {bill_id}: {data}")
                continue
            await conn.execute(
                "INSERT INTO bills (id, title, session) VALUES ($1, $2, $3) "
                "ON CONFLICT (id) DO NOTHING",
                bill_id, data.get("title", ""), data.get("session", ""),
            )
            inserted = await _insert_actions(conn, bill_id, data.get("actions", []))
            print(f"  OK   {bill_id}: {data.get('title', '')[:60]}  ({inserted} actions)")


async def seed_from_csv(csv_path: Path) -> None:
    print(f"\nImporting actions from {csv_path}...")
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    async with get_pool().acquire() as conn:
        bills_seen: set[str] = set()
        for order_num, row in enumerate(rows):
            bill_id = normalize_bill_id(row["Bill"])
            if bill_id not in bills_seen:
                await conn.execute(
                    "INSERT INTO bills (id, title, session) VALUES ($1, $2, $3) "
                    "ON CONFLICT (id) DO NOTHING",
                    bill_id, row.get("Webpage Title", ""), "2025-2026",
                )
                bills_seen.add(bill_id)
            await conn.execute(
                "INSERT INTO actions (bill_id, date, chamber, description, order_num) "
                "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (bill_id, order_num) DO NOTHING",
                bill_id, row["Date"], row["Chamber"], row["Action"], order_num,
            )
    print(f"  Imported {len(rows)} rows for {len(bills_seen)} bills.")


async def _insert_actions(conn, bill_id: str, actions: list[dict]) -> int:
    inserted = 0
    for action in actions:
        status = await conn.execute(
            "INSERT INTO actions (bill_id, date, chamber, description, order_num) "
            "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (bill_id, order_num) DO NOTHING",
            bill_id,
            action.get("date", ""),
            extract_chamber(action),
            action.get("description", ""),
            action.get("order", 0),
        )
        if status == "INSERT 0 1":
            inserted += 1
    return inserted


async def run(args) -> None:
    await create_pool()
    await init_db()

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

    if args.csv:
        await seed_from_csv(Path(args.csv))

    if not args.skip_api:
        await seed_from_openstates(bill_ids)

    await close_pool()
    print("\nMigration complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the tracker database from existing files.")
    parser.add_argument("--bills-file", default="Legislative Tracker Bills.txt")
    parser.add_argument("--csv", default=None)
    parser.add_argument("--skip-api", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
