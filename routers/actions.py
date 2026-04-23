from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from services.bills import get_actions
from services.openstates import normalize_bill_id

router = APIRouter(prefix="/api/actions", tags=["actions"])


@router.get("")
async def list_actions(bill_id: str | None = Query(default=None)) -> list[dict]:
    if bill_id:
        bill_id = normalize_bill_id(bill_id)
    return await get_actions(bill_id)


@router.get("/export")
async def export_actions() -> JSONResponse:
    """Download all cached actions as a JSON file."""
    return JSONResponse(
        content=await get_actions(),
        headers={
            "Content-Disposition": "attachment; filename=legislative_tracker_updates.json"
        },
    )
