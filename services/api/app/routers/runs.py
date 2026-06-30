from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class Stub(BaseModel):
    message: str


@router.get("/runs/{run_id}", response_model=Stub)
async def get_run(run_id: str):
    """Get a single check run result. [Sprint 2]"""
    return Stub(message=f"Run {run_id} — implemented in Sprint 2")
