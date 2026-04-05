from fastapi import APIRouter, HTTPException
from services.bills import fetch_all_updates
from services.openstates import RateLimitError

router = APIRouter(prefix="/api", tags=["fetch"])


@router.post("/fetch")
async def trigger_fetch() -> dict:
    """
    Pull the latest actions for all tracked bills from OpenStates.
    Fires all requests concurrently. Returns a summary of what changed.
    """
    try:
        return await fetch_all_updates()
    except RateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
