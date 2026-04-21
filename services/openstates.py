"""
OpenStates API v3 client.

All HTTP calls to https://v3.openstates.org live here.
Docs: https://v3.openstates.org/docs
"""

import re
import asyncio
import httpx
from config import OPENSTATES_API_KEY, OPENSTATES_BASE_URL, IL_JURISDICTION, IL_SESSION

# OpenStates free tier: 1 req/sec, 500 req/day
_REQUEST_INTERVAL = 1.1  # seconds between requests
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0  # seconds; doubled on each retry


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
    """Raised when OpenStates returns 429 and retries are exhausted."""
    pass


class DailyQuotaError(RateLimitError):
    """Raised when the daily 500-request quota is exhausted."""
    pass


def _parse_retry_after(resp: httpx.Response) -> float:
    """Return seconds to wait from Retry-After header, or a default."""
    try:
        return float(resp.headers.get("Retry-After", _RETRY_BASE_DELAY))
    except (ValueError, TypeError):
        return _RETRY_BASE_DELAY


async def _fetch_one(
    client: httpx.AsyncClient, bill_id: str
) -> tuple[str, dict | Exception]:
    """
    Fetch a single bill with all actions. Retries on transient 429s using
    Retry-After header. Returns (bill_id, data_or_exception).
    """
    params = {
        "jurisdiction": IL_JURISDICTION,
        "identifier": to_openstates_identifier(bill_id),
        "session": IL_SESSION,
        "include": ["actions", "sources"],
        "per_page": 1,
    }

    delay = _RETRY_BASE_DELAY
    for attempt in range(_MAX_RETRIES):
        try:
            resp = await client.get("/bills", params=params, timeout=15.0)

            if resp.status_code == 429:
                try:
                    body = resp.json()
                except Exception:
                    body = {}
                detail = body.get("detail", "")

                # Daily quota exhausted — no point retrying
                if "daily" in detail.lower() or "quota" in detail.lower():
                    return bill_id, DailyQuotaError(
                        f"OpenStates daily quota exhausted. Try again tomorrow. ({detail})"
                    )

                # Per-second rate limit — wait and retry
                wait = _parse_retry_after(resp)
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(wait * (2 ** attempt))
                    continue

                return bill_id, RateLimitError(
                    f"OpenStates rate limit exceeded after {_MAX_RETRIES} retries. ({detail})"
                )

            resp.raise_for_status()
            results = resp.json().get("results", [])
            if not results:
                return bill_id, ValueError(f"No results found for {bill_id} in session {IL_SESSION}")
            return bill_id, results[0]

        except (RateLimitError, DailyQuotaError):
            raise
        except httpx.TimeoutException:
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            return bill_id, TimeoutError(f"Request timed out for {bill_id} after {_MAX_RETRIES} attempts")
        except Exception as exc:
            return bill_id, exc

    return bill_id, RateLimitError(f"Gave up on {bill_id} after {_MAX_RETRIES} retries")


async def fetch_bills(bill_ids: list[str]) -> list[tuple[str, dict | Exception]]:
    """
    Fetch bills sequentially from OpenStates, respecting the 1 req/sec limit.
    Aborts early if the daily quota is exhausted, returning partial results.
    Returns list of (bill_id, data_or_exception) in the same order as bill_ids.
    """
    if not OPENSTATES_API_KEY:
        raise RuntimeError("OPENSTATES_API_KEY is not set. Add it to your .env file.")

    headers = {"X-API-KEY": OPENSTATES_API_KEY}
    results: list[tuple[str, dict | Exception]] = []

    async with httpx.AsyncClient(base_url=OPENSTATES_BASE_URL, headers=headers) as client:
        for i, bill_id in enumerate(bill_ids):
            result = await _fetch_one(client, bill_id)
            results.append(result)

            # Daily quota hit — tag remaining bills and stop
            if isinstance(result[1], DailyQuotaError):
                quota_err = result[1]
                for remaining in bill_ids[i + 1:]:
                    results.append((remaining, quota_err))
                break

            # Throttle between requests (skip delay after the last one)
            if i < len(bill_ids) - 1:
                await asyncio.sleep(_REQUEST_INTERVAL)

    return results
