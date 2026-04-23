from datetime import datetime, timezone, timedelta
from database import get_pool
from services.openstates import fetch_bills, extract_chamber, RateLimitError, DailyQuotaError

CACHE_HOURS = 12


async def get_all_bills() -> list[dict]:
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, session, added_at, note, source_url FROM bills ORDER BY id"
        )
        return [dict(r) for r in rows]


async def bill_exists(bill_id: str) -> bool:
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM bills WHERE id = $1", bill_id)
        return row is not None


async def remove_bill(bill_id: str) -> bool:
    async with get_pool().acquire() as conn:
        status = await conn.execute("DELETE FROM bills WHERE id = $1", bill_id)
        return status == "DELETE 1"


async def update_bill_note(bill_id: str, note: str) -> bool:
    async with get_pool().acquire() as conn:
        status = await conn.execute(
            "UPDATE bills SET note = $1 WHERE id = $2", note, bill_id
        )
        return status == "UPDATE 1"


async def get_actions(bill_id: str | None = None) -> list[dict]:
    async with get_pool().acquire() as conn:
        if bill_id:
            rows = await conn.fetch(
                "SELECT bill_id, date, chamber, description FROM actions "
                "WHERE bill_id = $1 ORDER BY order_num",
                bill_id,
            )
        else:
            rows = await conn.fetch(
                "SELECT bill_id, date, chamber, description FROM actions "
                "ORDER BY bill_id, order_num"
            )
        return [dict(r) for r in rows]


async def add_bill(bill_id: str) -> dict:
    results = await fetch_bills([bill_id])
    _, data = results[0]
    if isinstance(data, Exception):
        raise data

    title = data.get("title", "")
    session = data.get("session", "")
    sources = data.get("sources", [])
    source_url = sources[0].get("url", "") if sources else ""

    async with get_pool().acquire() as conn:
        await conn.execute(
            "INSERT INTO bills (id, title, session, source_url) VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (id) DO NOTHING",
            bill_id, title, session, source_url,
        )
        await _upsert_actions(conn, bill_id, data.get("actions", []))

    return {"id": bill_id, "title": title, "session": session}


async def fetch_all_updates() -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=CACHE_HOURS)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT id FROM bills WHERE last_fetched_at IS NULL OR last_fetched_at < $1",
            cutoff_str,
        )
        bill_ids = [r["id"] for r in rows]

    if not bill_ids:
        return {
            "updated": 0, "new_actions": 0, "errors": [],
            "skipped": "all bills fetched within the last 12 hours",
        }

    results = await fetch_bills(bill_ids)

    quota_hits = [r for r in results if isinstance(r[1], DailyQuotaError)]
    if quota_hits:
        fetched = len(results) - len(quota_hits)
        raise DailyQuotaError(
            f"{str(quota_hits[0][1])} ({fetched} of {len(bill_ids)} bills fetched before quota was hit)"
        )

    rate_limited = [r for r in results if isinstance(r[1], RateLimitError)]
    if len(rate_limited) == len(results):
        raise RateLimitError(str(rate_limited[0][1]))

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    new_actions = 0
    errors = []

    async with get_pool().acquire() as conn:
        for bill_id, data in results:
            if isinstance(data, Exception):
                errors.append({"bill_id": bill_id, "error": str(data)})
                continue
            sources = data.get("sources", [])
            source_url = sources[0].get("url", "") if sources else ""
            await conn.execute(
                "UPDATE bills SET title = $1, session = $2, last_fetched_at = $3, source_url = $4 "
                "WHERE id = $5",
                data.get("title", ""), data.get("session", ""), now_str, source_url, bill_id,
            )
            new_actions += await _upsert_actions(conn, bill_id, data.get("actions", []))

    return {"updated": len(bill_ids) - len(errors), "new_actions": new_actions, "errors": errors}


async def _upsert_actions(conn, bill_id: str, actions: list[dict]) -> int:
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
