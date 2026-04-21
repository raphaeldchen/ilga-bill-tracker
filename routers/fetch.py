from fastapi import APIRouter, Depends, HTTPException
from services.bills import fetch_all_updates
from services.openstates import RateLimitError, DailyQuotaError
from routers.auth import require_admin

router = APIRouter(prefix="/api", tags=["fetch"])


@router.post("/fetch", dependencies=[Depends(require_admin)])
async def trigger_fetch() -> dict:
    """
    Pull the latest actions for all tracked bills from OpenStates.
    Requests are sequential (1.1s apart) to respect the 1 req/sec rate limit.
    Returns a summary of what changed.
    """
    try:
        return await fetch_all_updates()
    except DailyQuotaError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except RateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
