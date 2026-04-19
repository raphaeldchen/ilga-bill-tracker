from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services.bills import get_all_bills, bill_exists, remove_bill, add_bill, update_bill_note
from services.openstates import normalize_bill_id
from routers.auth import require_admin

router = APIRouter(prefix="/api/bills", tags=["bills"])


class AddBillRequest(BaseModel):
    bill_id: str


class UpdateNoteRequest(BaseModel):
    note: str


@router.get("")
def list_bills() -> list[dict]:
    return get_all_bills()


@router.post("", status_code=201, dependencies=[Depends(require_admin)])
async def create_bill(body: AddBillRequest) -> dict:
    bill_id = normalize_bill_id(body.bill_id)
    if bill_exists(bill_id):
        raise HTTPException(status_code=409, detail=f"{bill_id} is already tracked")
    try:
        return await add_bill(bill_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{bill_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_bill(bill_id: str) -> None:
    if not remove_bill(normalize_bill_id(bill_id)):
        raise HTTPException(status_code=404, detail=f"{bill_id} not found")


@router.put("/{bill_id}/note", dependencies=[Depends(require_admin)])
def update_note(bill_id: str, body: UpdateNoteRequest) -> dict:
    normalized = normalize_bill_id(bill_id)
    if not update_bill_note(normalized, body.note):
        raise HTTPException(status_code=404, detail=f"{bill_id} not found")
    return {"bill_id": normalized, "note": body.note}
