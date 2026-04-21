import sqlite3
from datetime import datetime, timezone, timedelta
from database import get_connection
from services.openstates import fetch_bills, extract_chamber, RateLimitError, DailyQuotaError

CACHE_HOURS = 12


def get_all_bills() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, session, added_at, note, source_url FROM bills ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


def bill_exists(bill_id: str) -> bool:
    with get_connection() as conn:
        return conn.execute(
            "SELECT 1 FROM bills WHERE id = ?", (bill_id,)
        ).fetchone() is not None


def remove_bill(bill_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
        return cur.rowcount > 0


def update_bill_note(bill_id: str, note: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE bills SET note = ? WHERE id = ?", (note, bill_id)
        )
        return cur.rowcount > 0


def get_actions(bill_id: str | None = None) -> list[dict]:
    with get_connection() as conn:
        if bill_id:
            rows = conn.execute(
                """SELECT bill_id, date, chamber, description
                   FROM actions WHERE bill_id = ? ORDER BY order_num""",
                (bill_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT bill_id, date, chamber, description
                   FROM actions ORDER BY bill_id, order_num"""
            ).fetchall()
        return [dict(r) for r in rows]


async def add_bill(bill_id: str) -> dict:
    """
    Validate the bill exists on OpenStates, then insert it and its
    initial action history into the database.
    """
    results = await fetch_bills([bill_id])
    _, data = results[0]
    if isinstance(data, Exception):
        raise data

    title = data.get("title", "")
    session = data.get("session", "")
    sources = data.get("sources", [])
    source_url = sources[0].get("url", "") if sources else ""

    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO bills (id, title, session, source_url) VALUES (?, ?, ?, ?)",
            (bill_id, title, session, source_url),
        )
        _upsert_actions(conn, bill_id, data.get("actions", []))

    return {"id": bill_id, "title": title, "session": session}


async def fetch_all_updates() -> dict:
    """
    Pull the latest actions for every tracked bill from OpenStates.
    Bills fetched within the last CACHE_HOURS are skipped.
    Inserts only actions not already in the database.
    Returns a summary dict.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=CACHE_HOURS)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id FROM bills WHERE last_fetched_at IS NULL OR last_fetched_at < ?",
            (cutoff_str,),
        ).fetchall()
        bill_ids = [r[0] for r in rows]

    if not bill_ids:
        return {"updated": 0, "new_actions": 0, "errors": [], "skipped": "all bills fetched within the last 12 hours"}

    results = await fetch_bills(bill_ids)

    new_actions = 0
    errors = []

    # Daily quota hit: raise immediately (no point processing partial data as "errors")
    quota_hits = [r for r in results if isinstance(r[1], DailyQuotaError)]
    if quota_hits:
        fetched = len(results) - len(quota_hits)
        raise DailyQuotaError(
            f"{str(quota_hits[0][1])} ({fetched} of {len(bill_ids)} bills fetched before quota was hit)"
        )

    # If every result is a transient rate limit error, raise once.
    rate_limited = [r for r in results if isinstance(r[1], RateLimitError)]
    if len(rate_limited) == len(results):
        raise RateLimitError(str(rate_limited[0][1]))

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        for bill_id, data in results:
            if isinstance(data, Exception):
                errors.append({"bill_id": bill_id, "error": str(data)})
                continue
            sources = data.get("sources", [])
            source_url = sources[0].get("url", "") if sources else ""
            conn.execute(
                "UPDATE bills SET title = ?, session = ?, last_fetched_at = ?, source_url = ? WHERE id = ?",
                (data.get("title", ""), data.get("session", ""), now_str, source_url, bill_id),
            )
            new_actions += _upsert_actions(conn, bill_id, data.get("actions", []))

    return {
        "updated": len(bill_ids) - len(errors),
        "new_actions": new_actions,
        "errors": errors,
    }


def _upsert_actions(
    conn: sqlite3.Connection, bill_id: str, actions: list[dict]
) -> int:
    """INSERT OR IGNORE actions. Returns the number of newly inserted rows."""
    inserted = 0
    for action in actions:
        cur = conn.execute(
            """INSERT OR IGNORE INTO actions (bill_id, date, chamber, description, order_num)
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
