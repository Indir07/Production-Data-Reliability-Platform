from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class Stub(BaseModel):
    message: str


@router.get("/checks", response_model=Stub)
async def list_checks():
    """List all check definitions. [Sprint 2]"""
    return Stub(message="Checks endpoint — implemented in Sprint 2")


@router.post("/checks", response_model=Stub, status_code=201)
async def create_check():
    """Create a new check definition. [Sprint 2]"""
    return Stub(message="Create Check — implemented in Sprint 2")


@router.post("/checks/{check_id}/run", response_model=Stub)
async def trigger_check(check_id: str):
    """Manually trigger a check run. [Sprint 2]"""
    return Stub(message=f"Trigger run for check {check_id} — implemented in Sprint 2")
