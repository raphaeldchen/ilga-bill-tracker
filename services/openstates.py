"""
OpenStates API v3 client.

All HTTP calls to https://v3.openstates.org live here.
Docs: https://v3.openstates.org/docs
"""

import re
import asyncio
import httpx
from config import OPENSTATES_API_KEY, OPENSTATES_BASE_URL, IL_JURISDICTION, IL_SESSION


def normalize_bill_id(raw: str) -> str:
    """
    Normalize user-supplied bill IDs to uppercase, no spaces.
    'hb 1288' -> 'HB1288',  'SB 0086' -> 'SB0086'
    """
    return re.sub(r"\s+", "", raw.strip().upper())


def to_openstates_identifier(bill_id: str) -> str:
    """
    OpenStates expects a space between the type prefix and number.
    'HB1288' -> 'HB 1288'
    """
    m = re.match(r"^([A-Z]+)(\d+)$", bill_id)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return bill_id


def extract_chamber(action: dict) -> str:
    """Map OpenStates organization classification to 'House' or 'Senate'."""
    org = action.get("organization", {})
    classification = org.get("classification", "")
    if classification == "lower":
        return "House"
    if classification == "upper":
        return "Senate"
    # Fallback: check org name string
    name = org.get("name", "")
    if "House" in name:
        return "House"
    if "Senate" in name:
        return "Senate"
    return classification or "Unknown"


class RateLimitError(Exception):
    pass


async def _fetch_one(
    client: httpx.AsyncClient, bill_id: str
) -> tuple[str, dict | Exception]:
    """Fetch a single bill with all actions. Returns (bill_id, data_or_exception)."""
    try:
        params = {
            "jurisdiction": IL_JURISDICTION,
            "identifier": to_openstates_identifier(bill_id),
            "session": IL_SESSION,
            "include": "actions",
            "per_page": 1,
        }
        resp = await client.get("/bills", params=params, timeout=15.0)
        if resp.status_code == 429:
            detail = resp.json().get("detail", "rate limit exceeded")
            return bill_id, RateLimitError(f"OpenStates rate limit exceeded ({detail}). Try again tomorrow.")
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return bill_id, ValueError(f"No results found for {bill_id} in session {IL_SESSION}")
        return bill_id, results[0]
    except RateLimitError:
        raise
    except Exception as exc:
        return bill_id, exc


async def fetch_bills(bill_ids: list[str]) -> list[tuple[str, dict | Exception]]:
    """
    Fetch multiple bills concurrently from OpenStates.
    Returns list of (bill_id, data_or_exception) in the same order as bill_ids.
    """
    if not OPENSTATES_API_KEY:
        raise RuntimeError("OPENSTATES_API_KEY is not set. Add it to your .env file.")

    headers = {"X-API-KEY": OPENSTATES_API_KEY}
    async with httpx.AsyncClient(base_url=OPENSTATES_BASE_URL, headers=headers) as client:
        tasks = [_fetch_one(client, bid) for bid in bill_ids]
        return list(await asyncio.gather(*tasks))
